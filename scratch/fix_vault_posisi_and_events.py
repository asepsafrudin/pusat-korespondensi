import os
import sys
import psycopg
from dotenv import load_dotenv

load_dotenv()

def backfill_posisi_vault():
    dsn = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DATABASE')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                print("Updating posisi in surat_keluar_puu from raw_pool...")
                cur.execute("""
                    UPDATE surat_keluar_puu sk
                    SET posisi = rp.posisi
                    FROM korespondensi_raw_pool rp
                    WHERE sk.raw_pool_id = rp.id AND (sk.posisi IS NULL OR sk.posisi = '')
                """)
                print(f"Updated {cur.rowcount} records.")
                
                print("Inserting initial vault_events...")
                cur.execute("""
                    INSERT INTO vault_events (letter_id, event_type, event_value, event_at)
                    SELECT s.id, 'posisi_change', s.posisi, NOW()
                    FROM surat_keluar_puu s
                    LEFT JOIN vault_events ve ON ve.letter_id = s.id
                    WHERE ve.id IS NULL AND s.posisi IS NOT NULL AND s.posisi <> ''
                """)
                print(f"Inserted {cur.rowcount} events.")
                
            conn.commit()
    except Exception as e:
        print(f"Backfill failed: {e}")

if __name__ == "__main__":
    backfill_posisi_vault()
