import json
import os
import psycopg
from dotenv import load_dotenv

# Load env from parent directory (/home/aseps/MCP/.env)
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".env")
load_dotenv(dotenv_path)

JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "master_struktur_bangda2026.json")
DB_URL = os.getenv("DATABASE_URL")

def flatten_personnel(data):
    personnel = []
    units = data.get("struktur_organisasi_lengkap", {}).get("unit_kerja", [])
    
    for u in units:
        unit_id = u.get("id")
        
        # 1. Pimpinan
        p = u.get("pimpinan")
        if p:
            personnel.append({
                "unit_id": unit_id,
                "nama": p.get("nama"),
                "nip": p.get("nip"),
                "pangkat": p.get("pangkat"),
                "status": "PNS",
                "jabatan": p.get("jabatan"),
                "tim": "Struktural"
            })
            
        # 2. Tata Usaha
        tu = u.get("tata_usaha", {})
        if tu:
            k = tu.get("kepala") or tu.get("plt_kepala")
            if k:
                personnel.append({
                    "unit_id": unit_id,
                    "nama": k.get("nama"),
                    "nip": k.get("nip"),
                    "pangkat": k.get("pangkat"),
                    "status": "PNS",
                    "jabatan": "Kepala Tata Usaha",
                    "tim": "Tata Usaha"
                })
            for s in tu.get("staf", []):
                if isinstance(s, dict):
                    personnel.append({
                        "unit_id": unit_id,
                        "nama": s.get("nama"),
                        "nip": s.get("nip"),
                        "pangkat": s.get("pangkat"),
                        "status": s.get("status_kepegawaian", "PNS"),
                        "jabatan": "Staf Tata Usaha",
                        "tim": "Tata Usaha"
                    })
        
        # 3. Kelompok Jabatan Fungsional
        kjf = u.get("kelompok_jabatan_fungsional", {})
        for m in kjf.get("anggota", []):
             personnel.append({
                "unit_id": unit_id,
                "nama": m.get("nama"),
                "nip": m.get("nip"),
                "pangkat": m.get("pangkat"),
                "status": m.get("status_kepegawaian", "PNS"),
                "jabatan": m.get("jabatan_fungsional") or "Fungsional",
                "tim": kjf.get("nama") or "Kelompok Fungsional"
            })

        # 4. Sub Unit (Bagian/Subdit)
        for sub in u.get("sub_unit", []):
            sub_name = sub.get("nama_bagian") or sub.get("nama_subdit")
            lead = sub.get("penanggung_jawab") or sub.get("kepala_bagian")
            if lead:
                personnel.append({
                    "unit_id": unit_id,
                    "nama": lead.get("nama"),
                    "nip": lead.get("nip"),
                    "pangkat": lead.get("pangkat"),
                    "status": "PNS",
                    "jabatan": f"PJ {sub_name}",
                    "tim": sub_name
                })
            
            for tim in sub.get("tim_kerja", []):
                ketua = tim.get("ketua")
                if ketua:
                    personnel.append({
                        "unit_id": unit_id,
                        "nama": ketua.get("nama"),
                        "nip": ketua.get("nip"),
                        "pangkat": ketua.get("pangkat"),
                        "status": "PNS",
                        "jabatan": f"Ketua {tim.get('nama_tim')}",
                        "tim": tim.get("nama_tim")
                    })
                
                # PIC Korespondensi
                pic = tim.get("pic_korespondensi")
                if pic:
                    personnel.append({
                        "unit_id": unit_id,
                        "nama": pic.get("nama"),
                        "nip": pic.get("nip"),
                        "pangkat": pic.get("pangkat"),
                        "status": "PNS",
                        "jabatan": f"PIC {tim.get('nama_tim')}",
                        "tim": tim.get("nama_tim")
                    })

        # 5. Staf Operasional (NEW)
        for s in u.get("staf_operasional", []):
            personnel.append({
                "unit_id": unit_id,
                "nama": s.get("nama"),
                "nip": s.get("nip"),
                "pangkat": s.get("pangkat"),
                "status": s.get("status_kepegawaian"),
                "jabatan": s.get("jabatan_fungsional"),
                "tim": s.get("penugasan_tim"),
                "grade": s.get("grade_pppk")
            })

        # 6. Unit Khusus (NEW)
        uk = u.get("unit_khusus", {})
        for uk_name, members in uk.items():
            for m in members:
                personnel.append({
                    "unit_id": unit_id,
                    "nama": m.get("nama"),
                    "nip": m.get("nip"),
                    "pangkat": m.get("pangkat"),
                    "status": m.get("status_kepegawaian"),
                    "jabatan": m.get("jabatan_fungsional"),
                    "tim": uk_name.replace("_", " ").upper()
                })

    return personnel

def sync():
    if not os.path.exists(JSON_PATH):
        print(f"Error: {JSON_PATH} not found")
        return

    with open(JSON_PATH, 'r') as f:
        data = json.load(f)

    all_personnel = flatten_personnel(data)
    print(f"Flattened {len(all_personnel)} personnel from JSON")

    try:
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                # Optional: Clear existing or use UPSERT balance
                # For safety and completeness in this migration, we'll use UPSERT on 'nama' 
                # (Note: In production, NIP is better, but some records lack NIP)
                
                success_count = 0
                for p in all_personnel:
                    nama_raw = p.get("nama")
                    if not nama_raw or nama_raw == "-": continue
                    
                    nama = nama_raw.upper().strip()
                    
                    cur.execute("""
                        INSERT INTO staff_details 
                        (unit_id, nama, nip, pangkat, status_kepegawaian, jabatan_fungsional, penugasan_tim, grade_pppk)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (nama) DO UPDATE SET
                            unit_id = EXCLUDED.unit_id,
                            nip = COALESCE(EXCLUDED.nip, staff_details.nip),
                            pangkat = COALESCE(EXCLUDED.pangkat, staff_details.pangkat),
                            status_kepegawaian = COALESCE(EXCLUDED.status_kepegawaian, staff_details.status_kepegawaian),
                            jabatan_fungsional = COALESCE(EXCLUDED.jabatan_fungsional, staff_details.jabatan_fungsional),
                            penugasan_tim = COALESCE(EXCLUDED.penugasan_tim, staff_details.penugasan_tim),
                            grade_pppk = COALESCE(EXCLUDED.grade_pppk, staff_details.grade_pppk)
                    """, (
                        p.get("unit_id"),
                        nama,
                        p.get("nip"),
                        p.get("pangkat"),
                        p.get("status"),
                        p.get("jabatan"),
                        p.get("tim"),
                        p.get("grade")
                    ))
                    success_count += 1
                
                conn.commit()
                print(f"Successfully synced {success_count} personnel to database.")

    except Exception as e:
        print(f"Database Error: {e}")

if __name__ == "__main__":
    sync()
