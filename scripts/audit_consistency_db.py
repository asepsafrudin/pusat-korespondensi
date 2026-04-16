import os
import sys
import psycopg
from dotenv import load_dotenv
from pathlib import Path

# Tambahkan project root dan folder korespondensi-server ke path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "korespondensi-server"))

from src.parser_nomor_nd import NomorNDParser

# Load environment variables
load_dotenv(project_root / ".env")

def run_audit():
    # Inisialisasi Parser
    parser = NomorNDParser(
        referensi_path=str(project_root / "korespondensi-server/docs/kodefikasi_arsip_referensi.json"),
        struktur_path=str(project_root / "korespondensi-server/src/master_struktur_bangda_2025.json")
    )
    
    # Koneksi Database
    conn_str = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DATABASE')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    
    try:
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                print("🔍 Memulai Audit Konsistensi & Spesifikasi (Target: Korespondensi Raw Pool)...")
                
                # Bersihkan tabel audit lama
                cur.execute("TRUNCATE TABLE audit_notifications")
                
                # Ambil data dari tabel pusat (Hanya grup INTERNAL)
                cur.execute("""
                    SELECT unique_id, nomor_nd, hal 
                    FROM korespondensi_raw_pool 
                    WHERE data_group = 'INTERNAL' AND nomor_nd IS NOT NULL
                """)
                rows = cur.fetchall()
                
                total_checked = 0
                anomalies_found = 0
                
                for row in rows:
                    uid, no_nd, hal = row
                    total_checked += 1
                    
                    # Lakukan parsing dan audit
                    result = parser.parse(no_nd, hal)
                    report = result.get("validation_report", {})
                    messages = report.get("messages", [])
                    
                    if no_nd == '800/296/TU/SUPD.III':
                        print(f"  [DEBUG] Memproses sampel kritis {no_nd}")
                        print(f"  [DEBUG] Pesan dari Parser: {messages}")
                    
                    # Cek apakah ada Anomali atau Saran Spesifikasi
                    has_anomaly = not report.get("is_consistent")
                    has_suggestion = any("💡 Saran Spesifikasi" in m for m in messages)
                    
                    if has_anomaly or has_suggestion:
                        anomalies_found += 1
                        score = result.get("anomali_score", 0)
                        
                        # Gabungkan pesan
                        notif_msg = "; ".join([m for m in messages if "Saran Spesifikasi" not in m])
                        if not notif_msg: notif_msg = "Konsistensi Dasar Terpenuhi"
                        
                        # Cari Saran Spesifikasi Khusus
                        suggestion = "Mohon periksa kembali kesesuaian kode."
                        spec_sug = next((m for m in messages if "💡 Saran Spesifikasi" in m), None)
                        if spec_sug:
                            suggestion = spec_sug
                            print(f"  [i] Ditemukan Saran untuk {no_nd}: {suggestion[:50]}...")
                        
                        # Tentukan Tema jika ada anomali substansi
                        detected_theme = "General"
                        for m in messages:
                            if "Tema '" in m:
                                import re
                                theme_match = re.search(r"Tema '([^']+)'", m)
                                if theme_match: detected_theme = theme_match.group(1)

                        # Simpan ke Database
                        cur.execute("""
                            INSERT INTO audit_notifications 
                            (unique_id, nomor_nd, hal, detected_theme, suggested_prefix, anomaly_score, message, suggestion, deskripsi_kode)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (uid, no_nd, hal, detected_theme, detected_theme, score, notif_msg, suggestion, report.get("deskripsi_arsip", "Unknown")))
                        
                        if total_checked % 100 == 0:
                            print(f"  ... Diproses {total_checked} dokumen")
                
                conn.commit()
                print(f"\n✅ Audit Selesai & Berhasil Disimpan.")
                print(f"Total Dokumen Diperiksa: {total_checked}")
                print(f"Total Temuan (Anomali + Saran): {anomalies_found}")
                
    except Exception as e:
        print(f"❌ Terjadi kesalahan saat audit: {e}")

if __name__ == "__main__":
    run_audit()
