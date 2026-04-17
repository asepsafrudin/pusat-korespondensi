import os
import sys
import psycopg
from dotenv import load_dotenv

load_dotenv()

# Add necessary paths
PROJECT_ROOT = "/home/aseps/MCP/mcp-unified"
sys.path.insert(0, PROJECT_ROOT)

from integrations.korespondensi.utils import determine_refined_status

def backfill_refined_statuses():
    dsn = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DATABASE')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                print("Backfilling surat_masuk_puu_internal...")
                cur.execute("SELECT id, posisi FROM surat_masuk_puu_internal")
                rows = cur.fetchall()
                for r_id, posisi in rows:
                    status = determine_refined_status(posisi)
                    cur.execute("UPDATE surat_masuk_puu_internal SET status_pengiriman = %s WHERE id = %s", (status, r_id))
                
                print("Backfilling surat_keluar_puu...")
                # surat_keluar_puu doesn't have posisi, but we can try to fetch it from raw_pool
                cur.execute("""
                    SELECT sk.id, rp.posisi 
                    FROM surat_keluar_puu sk
                    JOIN korespondensi_raw_pool rp ON rp.id = sk.raw_pool_id
                """)
                rows_keluar = cur.fetchall()
                for sk_id, posisi in rows_keluar:
                    status = determine_refined_status(posisi)
                    # For Vault, if it's already in surat_keluar, and status is still 'Dalam Proses', 
                    # we might want to default to 'Arsip Final' if no specific token found
                    if status == "Dalam Proses":
                        status = "Arsip Final"
                    cur.execute("UPDATE surat_keluar_puu SET status_pengiriman = %s WHERE id = %s", (status, sk_id))
                
                print("Backfill completed.")
            conn.commit()
    except Exception as e:
        print(f"Backfill failed: {e}")

if __name__ == "__main__":
    backfill_refined_statuses()
