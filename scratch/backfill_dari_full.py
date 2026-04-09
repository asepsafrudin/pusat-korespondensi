
import os
import re
from src.services.sync_service import map_dari_full
from src.database import execute_query, get_db_connection

def backfill_dari_full():
    """Populate dari_full for all records in internal table."""
    try:
        rows = execute_query("SELECT id, dari FROM surat_masuk_puu_internal")
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                count = 0
                for r in rows:
                    full_name = map_dari_full(r['dari'])
                    if full_name != r['dari']:
                        cur.execute("UPDATE surat_masuk_puu_internal SET dari_full = %s WHERE id = %s", [full_name, r['id']])
                        count += 1
                conn.commit()
                print(f"Backfilled dari_full for {count} records.")
    except Exception as e:
        print(f"Backfill failed: {e}")

if __name__ == "__main__":
    backfill_dari_full()
