import json
import os
from typing import List, Dict

# Path constants derived from ground truth audit
USER_P3K_PATH = "/home/aseps/MCP/mcp-data/document_management/storage/admin_data/struktur_organisasi/user_p3k.json"
MASTER_STRUKTUR_PATH = "/home/aseps/MCP/mcp-data/document_management/storage/admin_data/struktur_organisasi/master_struktur_bangda_2025.json"

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
                    name = row.get("Nama_Pegawai", "")
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
        if query_up in s["nama"].upper():
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
