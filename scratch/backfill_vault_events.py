import os
import sys
import psycopg
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Add necessary paths
PROJECT_ROOT = "/home/aseps/MCP/korespondensi-server"
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from database import execute_query

def backfill_vault_events():
    dsn = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DATABASE')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                print("Backfilling vault_events from surat_keluar_puu...")
                
                # Check if we already have events to avoid duplicates
                cur.execute("SELECT COUNT(*) FROM vault_events")
                if cur.fetchone()[0] > 0:
                    print("Vault events already have data. Skipping initial backfill.")
                    # Actually, let's force it for letters that have NO events
                    cur.execute("""
                        INSERT INTO vault_events (letter_id, event_type, event_value, event_at)
                        SELECT s.id, 'posisi_change', s.posisi, NOW()
                        FROM surat_keluar_puu s
                        LEFT JOIN vault_events ve ON ve.letter_id = s.id
                        WHERE ve.id IS NULL AND s.posisi IS NOT NULL AND s.posisi <> ''
                    """)
                else:
                    cur.execute("""
                        INSERT INTO vault_events (letter_id, event_type, event_value, event_at)
                        SELECT id, 'posisi_change', posisi, NOW()
                        FROM surat_keluar_puu
                        WHERE posisi IS NOT NULL AND posisi <> ''
                    """)
                
                print(f"Inserted {cur.rowcount} initial events into vault_events.")
            conn.commit()
    except Exception as e:
        print(f"Backfill failed: {e}")

if __name__ == "__main__":
    backfill_vault_events()
