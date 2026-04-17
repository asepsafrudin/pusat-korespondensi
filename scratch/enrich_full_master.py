import json
import re
from datetime import datetime

# Paths
input_path = '/home/aseps/MCP/korespondensi-server/src/master_struktur_bangda2026_enriched.json'
output_path = '/home/aseps/MCP/korespondensi-server/src/master_struktur_bangda2026_final.json'

def enrich_person(person):
    if not person or not isinstance(person, dict):
        return person

    # 1. Name & Education Enrichment
    nama_full = person.get('nama', '')
    if nama_full:
        gelar = person.get('gelar_akademik', [])
        # Check prefixes
        prefixes = ["dr.", "drg.", "apt.", "Ir.", "Drs.", "Dra.", "Prof.", "Dr."]
        for pref in prefixes:
            if nama_full.startswith(pref) and pref.strip('.') not in gelar:
                gelar.append(pref.strip('.'))
        
        # Check suffixes
        if ',' in nama_full:
            gelar_parts = nama_full.split(',')[1:]
            for g in gelar_parts:
                g_clean = g.strip()
                if g_clean not in gelar:
                    gelar.append(g_clean)
        
        person['gelar_akademik'] = list(set(gelar))

    # 2. NIP Enrichment (Gender & Birth Date)
    nip_raw = person.get('nip', '')
    if nip_raw and nip_raw != '-':
        nip_clean = nip_raw.replace(' ', '').replace('.', '')
        if len(nip_clean) >= 15:
            # Gender
            gender_digit = nip_clean[14]
            if 'jenis_kelamin' not in person or person['jenis_kelamin'] == "Tidak Diketahui":
                person['jenis_kelamin'] = "Laki-laki" if gender_digit == '1' else "Perempuan" if gender_digit == '2' else "Tidak Diketahui"
            
            # Birth Date
            if 'tanggal_lahir' not in person or not person['tanggal_lahir']:
                dob_str = nip_clean[:8]
                try:
                    person['tanggal_lahir'] = f"{dob_str[0:4]}-{dob_str[4:6]}-{dob_str[6:8]}"
                except:
                    pass

    # 3. Pangkat & Functional Enrichment
    pangkat_str = person.get('pangkat', '')
    jabatan_str = person.get('jabatan', '') or person.get('jabatan_fungsional', '')
    
    combined_text = (pangkat_str + " " + jabatan_str).upper()
    
    # Extract Golongan (e.g. IV/a)
    gol_match = re.search(r'\(([I|V|/|a|b|c|d]+)\)', pangkat_str)
    if gol_match:
        person['golongan'] = gol_match.group(1)
    
    # Extract Jenjang Fungsional
    jenjangs = {
        "UTAMA": "Ahli Utama",
        "MADYA": "Ahli Madya",
        "MUDA": "Ahli Muda",
        "PERTAMA": "Ahli Pertama",
        "MAHIR": "Terampil Mahir",
        "TERAMPIL": "Terampil",
        "PELAKSANA": "Pelaksana"
    }
    
    for key, val in jenjangs.items():
        if key in combined_text:
            person['jenjang_fungsional'] = val
            break

    # 4. Status Kepegawaian Inference
    if 'status_kepegawaian' not in person:
        if nip_raw and len(nip_raw.replace(' ', '')) == 18:
            person['status_kepegawaian'] = "PNS"
        elif 'grade_pppk' in person:
            person['status_kepegawaian'] = "PPPK"

    return person

def process_recursive(data):
    if isinstance(data, dict):
        # If it looks like a person object (has 'nama' or 'nip')
        if 'nama' in data or 'nip' in data:
            enrich_person(data)
        
        # Continue recursion
        for key, value in data.items():
            process_recursive(value)
    elif isinstance(data, list):
        for item in data:
            process_recursive(item)

def main():
    with open(input_path, 'r') as f:
        data = json.load(f)
    
    process_recursive(data)
    
    # Final metadata update
    data['metadata']['updated_at'] = datetime.now().isoformat()
    data['metadata']['version'] = "2.1-ENRICHED"
    data['metadata']['changelog'].append(f"FINAL ENRICH: Recursive analysis of all personnel (PNS & PPPK)")

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Full enrichment complete. Final master saved to {output_path}")

if __name__ == "__main__":
    main()
