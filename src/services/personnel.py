import json
import os
import re
from typing import List, Dict

# Path constants derived from ground truth audit
USER_P3K_PATH = "/home/aseps/MCP/mcp-data/document_management/storage/admin_data/struktur_organisasi/user_p3k.json"
MASTER_STRUKTUR_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "master_struktur_bangda2026.json")

def get_all_personnel_from_master() -> List[Dict]:
    """Helper to extract and flatten all unique personnel from master structure."""
    personnel = []
    try:
        if not os.path.exists(MASTER_STRUKTUR_PATH):
            return []
            
        with open(MASTER_STRUKTUR_PATH, 'r') as f:
            data = json.load(f)
            units = data.get("struktur_organisasi_lengkap", {}).get("unit_kerja", [])
            for u in units:
                unit_name = u.get("id")
                # Unit Leader
                if "pimpinan" in u:
                    personnel.append({"nama": u["pimpinan"]["nama"], "jabatan": u["pimpinan"]["jabatan"], "unit": unit_name})
                
                # Fungsional members
                if "kelompok_jabatan_fungsional" in u:
                    for m in u["kelompok_jabatan_fungsional"].get("anggota", []):
                        personnel.append({"nama": m["nama"], "jabatan": m.get("pangkat"), "unit": unit_name})

                # Sub Unit
                for sub in u.get("sub_unit", []):
                    # Bagian/Subdit Leader
                    for key in ["kepala_bagian", "penanggung_jawab"]:
                        if key in sub:
                            personnel.append({"nama": sub[key]["nama"], "jabatan": sub.get("nama_bagian") or sub.get("nama_subdit"), "unit": unit_name})
                    
                    # Tim Kerja
                    for t in sub.get("tim_kerja", []):
                        for key in ["ketua", "pic_korespondensi"]:
                            if key in t:
                                personnel.append({"nama": t[key]["nama"], "jabatan": t[key].get("jabatan") or t.get("nama_tim"), "unit": unit_name})

                # Staf Operasional (NEW in 2026)
                for s in u.get("staf_operasional", []):
                    personnel.append({
                        "nama": s["nama"], 
                        "jabatan": s.get("jabatan_fungsional") or "Staf Operasional", 
                        "unit": unit_name,
                        "nip": s.get("nip"),
                        "pangkat": s.get("pangkat")
                    })

                # Unit Khusus (NEW in 2026, e.g. Poliklinik)
                uk = u.get("unit_khusus", {})
                for uk_name, members in uk.items():
                    uk_label = uk_name.replace("_", " ").upper()
                    for m in members:
                        personnel.append({
                            "nama": m["nama"],
                            "jabatan": f"{uk_label} - {m.get('jabatan_fungsional', 'Staf')}",
                            "unit": unit_name,
                            "nip": m.get("nip"),
                            "pangkat": m.get("pangkat")
                        })

                # Tata Usaha
                tu = u.get("tata_usaha")
                if tu:
                    if "kepala" in tu:
                        personnel.append({"nama": tu["kepala"]["nama"], "jabatan": "Kepala Tata Usaha", "unit": unit_name})
                    for s in tu.get("staf", []):
                        if isinstance(s, dict):
                            personnel.append({"nama": s["nama"], "jabatan": "Staf Tata Usaha", "unit": unit_name})
                        else:
                            personnel.append({"nama": s, "jabatan": "Staf Tata Usaha", "unit": unit_name})
    except Exception as e:
        print(f"Error flattening master personnel: {e}")
    return personnel

def search_staff_pppk(query: str) -> List[Dict]:
    """Search for PPPK and Structural personnel by name."""
    if not query:
        return []
        
    res = []
    query_up = query.upper()
    
    # 1. Search in PPPK
    try:
        with open(USER_P3K_PATH, 'r') as f:
            data = json.load(f)
            sheets_data = data.get("sheets", {})
            for sheet_name in ["BANGDA", "SETJEN", "ADWIL"]:
                rows = sheets_data.get(sheet_name, {}).get("data", [])
                for row in rows:
                    name = row.get("Nama_Pegawai", "") or ""
                    if query_up in name.upper():
                        res.append({
                            "nama": name,
                            "jabatan": f"PPPK - {row.get('JABATAN', 'Staff')}",
                            "source": sheet_name
                        })
    except Exception as e:
        print(f"Error reading PPPK JSON: {e}")

    # 2. Search in Master Structure (Structural Personnel)
    master_staffs = get_all_personnel_from_master()
    for s in master_staffs:
        nama = s.get("nama") or ""
        if query_up in nama.upper():
            # Avoid duplicates if they appear in both
            if not any(r["nama"] == s["nama"] for r in res):
                res.append({
                    "nama": s["nama"],
                    "jabatan": f"{s['unit']} - {s['jabatan']}",
                    "source": "MASTER"
                })
        
    return res[:25] # Limit results for real-time search

def get_hukum_pics() -> List[Dict]:
    """Get personnel from the Hukum Work Group from master structure."""
    pics = []
    try:
        with open(MASTER_STRUKTUR_PATH, 'r') as f:
            data = json.load(f)
            units = data.get("struktur_organisasi_lengkap", {}).get("unit_kerja", [])
            for u in units:
                if u.get("id") == "SEKRETARIAT":
                    for sub in u.get("sub_unit", []):
                        if "Kelompok Substansi Hukum" in sub.get("nama_bagian", ""):
                            # Sub unit coordinator
                            pj = sub.get("penanggung_jawab")
                            if pj:
                                pics.append({"nama": pj["nama"], "jabatan": "Koordinator PUU", "is_pj": True})
                            
                            # Work teams
                            for t in sub.get("tim_kerja", []):
                                ketua = t.get("ketua")
                                if ketua:
                                    pics.append({
                                        "nama": ketua["nama"], 
                                        "jabatan": f"Ketua {t.get('nama_tim')}",
                                        "is_pj": False
                                    })
    except Exception as e:
        print(f"Error reading master structure: {e}")
        
    # Fallback if file not found or error
    if not pics:
        pics = [{"nama": "Asep", "jabatan": "Admin PUU"}, {"nama": "Dennis", "jabatan": "Officer"}]
        
    return pics

def get_unit_mapping() -> Dict[str, str]:
    """Get mapping of Unit ID -> Full Name with Leader."""
    mapping = {}
    try:
        if not os.path.exists(MASTER_STRUKTUR_PATH):
            return {}
            
        with open(MASTER_STRUKTUR_PATH, 'r') as f:
            data = json.load(f)
            units = data.get("struktur_organisasi_lengkap", {}).get("unit_kerja", [])
            for u in units:
                uid = u.get("id")
                name = u.get("nama_unit")
                pimpinan = u.get("pimpinan", {}).get("nama")
                if uid and name:
                    mapping[uid] = f"{name} ({pimpinan})" if pimpinan else name
                
                # Also index sub_units if they have IDs or names that act as codes
                for sub in u.get("sub_unit", []):
                    # We check for sub names that often appear in 'DARI' field
                    name_sub = sub.get("nama_bagian") or sub.get("nama_subdit")
                    if name_sub:
                        # Simple keys for mapping
                        if "HUKUM" in name_sub.upper():
                            mapping["PUU"] = f"{name_sub} ({sub.get('penanggung_jawab', {}).get('nama', '')})"
                        
                        # Extra patterns for SD (Subdit)
                        if "SUBDIT" in name_sub.upper():
                            # e.g. "Perencanaan dan Evaluasi Wilayah I" -> SD I
                            match = re.search(r'WILAYAH\s+([IVX]+)', name_sub.upper())
                            if match:
                                mapping[f"SD {match.group(1)}"] = name_sub
    except Exception as e:
        print(f"Error building unit mapping: {e}")
    return mapping

def get_unit_acronyms() -> List[str]:
    """Get list of all acronyms/IDs mentioned in the structure."""
    units = ["SES", "TU", "BU", "KEU", "PRC", "PUU", "PEIPD", "SUPD", "SD", "DIRJEN", "DITJEN", "BANGDA", "UMUM"]
    try:
        if not os.path.exists(MASTER_STRUKTUR_PATH):
            return units
            
        with open(MASTER_STRUKTUR_PATH, 'r') as f:
            data = json.load(f)
            units_json = data.get("struktur_organisasi_lengkap", {}).get("unit_kerja", [])
            for u in units_json:
                uid = u.get("id")
                if uid and uid not in units:
                    units.append(uid)
                # Handle SUPD names etc
                if "SUPD" in uid:
                    norm = uid.replace("_", " ")
                    if norm not in units: units.append(norm)
    except:
        pass
    return list(set(units))
