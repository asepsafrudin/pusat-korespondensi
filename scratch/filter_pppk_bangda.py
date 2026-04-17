import json
import os
from datetime import datetime

# Paths
source_path = '/home/aseps/MCP/mcp-data/document_management/storage/admin_data/struktur_organisasi/user_p3k.json'
master_path = '/home/aseps/MCP/korespondensi-server/src/master_struktur_bangda2026.json'
output_path = '/home/aseps/MCP/korespondensi-server/src/pppk_bangda_filtered.json'

def transform():
    # Load source data
    with open(source_path, 'r') as f:
        source_data = json.load(f)
    
    # Load master structure for template
    with open(master_path, 'r') as f:
        master_data = json.load(f)
    
    # Unit mapping keywords
    mapping = {
        'SEKRETARIAT': 'SEKRETARIAT',
        'PERENCANAAN, EVALUASI DAN INFORMASI': 'PEIPD',
        'PEMERINTAHAN DAERAH I': 'SUPD_I',
        'PEMERINTAHAN DAERAH II': 'SUPD_II',
        'PEMERINTAHAN DAERAH III': 'SUPD_III',
        'PEMERINTAHAN DAERAH IV': 'SUPD_IV'
    }

    # Prepare structure
    new_structure = {
        "metadata": {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "source_file": os.path.basename(source_path),
            "description": "Filtered PPPK data for Ditjen Bina Pembangunan Daerah"
        },
        "struktur_organisasi_lengkap": {
            "instansi": "DITJEN BINA PEMBANGUNAN DAERAH",
            "unit_kerja": []
        }
    }

    # Initialize unit dict to store people
    units_data = {uid: [] for uid in ['SEKRETARIAT', 'PEIPD', 'SUPD_I', 'SUPD_II', 'SUPD_III', 'SUPD_IV']}
    unmapped = []

    # Process all sheets
    for sheet_name, sheet in source_data['sheets'].items():
        for row in sheet['data']:
            jabatan_full = row.get('JABATAN') or ""
            if 'bina pembangunan daerah' in jabatan_full.lower():
                # Determine Unit
                unit_id = None
                for keyword, uid in mapping.items():
                    if keyword in jabatan_full.upper():
                        unit_id = uid
                        break
                
                # Default to SEKRETARIAT if it contains Bangda but no specific sub-unit keyword
                if not unit_id:
                    unit_id = 'SEKRETARIAT'

                # Clean Jabatan Fungsional (part before 'PADA')
                jabatan_fungsional = jabatan_full.split(' PADA ')[0].strip()
                
                # Detail Penugasan Tim (Extracting Bagian/Subdit/Subbag)
                penugasan_tim = "Belum Terdefinisikan"
                if " PADA " in jabatan_full.upper():
                    parts = jabatan_full.upper().split(' PADA ')
                    if len(parts) > 1:
                        detail = parts[1]
                        sub_keywords = ["SUBDIREKTORAT", "BAGIAN", "SUBBAGIAN", "KELOMPOK"]
                        found_detail = False
                        for sk in sub_keywords:
                            if sk in detail:
                                major_units = ["DIREKTORAT JENDERAL", "DIREKTORAT SINKRONISASI", "DIREKTORAT PERENCANAAN", "SEKRETARIAT DIREKTORAT"]
                                sub_part = detail[detail.find(sk):]
                                end_pos = len(sub_part)
                                for mu in major_units:
                                    mu_pos = sub_part.find(mu)
                                    if mu_pos != -1 and mu_pos < end_pos:
                                        end_pos = mu_pos
                                penugasan_tim = sub_part[:end_pos].strip().strip(',')
                                found_detail = True
                                break
                        if not found_detail:
                            major_units = ["DIREKTORAT JENDERAL", "DIREKTORAT SINKRONISASI", "DIREKTORAT PERENCANAAN", "SEKRETARIAT DIREKTORAT"]
                            end_pos = len(detail)
                            for mu in major_units:
                                mu_pos = detail.find(mu)
                                if mu_pos != -1 and mu_pos < end_pos:
                                    end_pos = mu_pos
                            remaining = detail[:end_pos].strip().strip(',')
                            if remaining and len(remaining) > 3:
                                penugasan_tim = remaining

                # --- NEW ENRICHMENT LOGIC ---
                
                # 1. NIP Analysis (Gender & Birth Date)
                nip_clean = row.get('N_I_P', '').replace(' ', '')
                jenis_kelamin = "Tidak Diketahui"
                tanggal_lahir = None
                if len(nip_clean) >= 15:
                    gender_digit = nip_clean[14]
                    jenis_kelamin = "Laki-laki" if gender_digit == '1' else "Perempuan" if gender_digit == '2' else "Tidak Diketahui"
                    
                    dob_str = nip_clean[:8]
                    try:
                        tanggal_lahir = f"{dob_str[0:4]}-{dob_str[4:6]}-{dob_str[6:8]}"
                    except:
                        pass

                # 2. Education Analysis (Degrees - Prefix & Suffix)
                nama_full = row.get('Nama_Pegawai', '')
                gelar = []
                
                # Check prefixes
                prefixes = ["dr.", "drg.", "apt.", "Ir.", "Drs.", "Dra."]
                for pref in prefixes:
                    if nama_full.startswith(pref):
                        gelar.append(pref.strip('.'))
                
                # Check suffixes
                if ',' in nama_full:
                    gelar_parts = nama_full.split(',')[1:]
                    gelar.extend([g.strip() for g in gelar_parts])
                
                # 3. Grade Inference (Mapping based on Jabatan & Education)
                grade_pppk = None
                jabatan_upper = jabatan_fungsional.upper()
                
                # Heuristic mapping for PPPK 2026
                if any(x in jabatan_upper for x in ["AHLI PERTAMA", "AHLI MUDA", "PENATA"]):
                    grade_pppk = "IX"
                elif any(x in jabatan_upper for x in ["TERAMPIL", "MAHIR", "PENGELOLA", "ASISTEN"]):
                    if "PENGELOLA" in jabatan_upper and any(edu in str(gelar).upper() for edu in ["S.", "SE", "ST", "SH", "SKM"]):
                        grade_pppk = "IX"
                    else:
                        grade_pppk = "VII"
                elif any(x in jabatan_upper for x in ["PENGADMINISTRASI", "OPERATOR", "PRAMU"]):
                    grade_pppk = "V"
                
                # 4. Final Penugasan Tim Detailing & Manual Overrides
                final_penugasan = penugasan_tim.title()
                
                # Manual Override for Asep Safrudin
                if "ASEP SAFRUDIN" in nama_full.upper():
                    final_penugasan = "Tim Dokumentasi Dan Informasi Hukum"
                
                # Default mapping for Unmapped
                if final_penugasan == "Belum Terdefinisikan":
                    if any(x in str(gelar) for x in ["dr", "drg", "Ners"]) or any(x in jabatan_upper for x in ["DOKTER", "GIGI", "PERAWAT", "BIDAN", "MEDIS", "KESEHATAN"]):
                        final_penugasan = "Poliklinik Pratama"
                    elif unit_id == "SEKRETARIAT":
                        final_penugasan = "Sekretariat Ditjen (Umum)"
                    else:
                        final_penugasan = f"Layanan Direktorat {unit_id.replace('_', ' ')}"

                # --- END ENRICHMENT LOGIC ---

                # Create person object
                person = {
                    "nama": nama_full,
                    "nip": row.get('N_I_P'),
                    "jenis_kelamin": jenis_kelamin,
                    "tanggal_lahir": tanggal_lahir,
                    "gelar_akademik": list(set(gelar)),
                    "pangkat": "", 
                    "status_kepegawaian": "PPPK",
                    "jabatan_fungsional": jabatan_fungsional,
                    "penugasan_tim": final_penugasan,
                    "grade_pppk": grade_pppk
                }
                
                units_data[unit_id].append(person)

    # Build final structure based on units in master
    for unit in master_data['struktur_organisasi_lengkap']['unit_kerja']:
        uid = unit['id']
        if uid in units_data:
            new_unit = {
                "id": uid,
                "nama_unit": unit['nama_unit'],
                "staf_operasional": units_data[uid]
            }
            new_structure['struktur_organisasi_lengkap']['unit_kerja'].append(new_unit)

    # Save to file
    with open(output_path, 'w') as f:
        json.dump(new_structure, f, indent=2)
    
    print(f"Successfully created {output_path} with {sum(len(v) for v in units_data.values())} records.")

if __name__ == "__main__":
    transform()
