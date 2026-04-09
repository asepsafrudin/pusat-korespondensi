
import os
from src.database import execute_query, get_db_connection

def fix_legacy_timeline():
    """Migrasi data posisi untuk baris yang sudah terlanjur di-sync tanpa posisi."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Update posisi di internal dari raw_pool
                cur.execute("""
                    UPDATE surat_masuk_puu_internal s
                    SET posisi = r.posisi
                    FROM korespondensi_raw_pool r
                    WHERE s.raw_pool_id = r.id AND (s.posisi IS NULL OR s.posisi = '');
                """)
                updated_count = cur.rowcount
                print(f"Updated 'posisi' for {updated_count} letters.")

                # 2. Insert missing initial events
                cur.execute("""
                    INSERT INTO correspondence_events (letter_id, event_type, event_value, event_at)
                    SELECT s.id, 'posisi_change', s.posisi, COALESCE(s.tanggal_diterima_puu, s.created_at, NOW())
                    FROM surat_masuk_puu_internal s
                    WHERE s.posisi IS NOT NULL AND s.posisi != ''
                    AND s.id NOT IN (SELECT letter_id FROM correspondence_events);
                """)
                events_count = cur.rowcount
                print(f"Created {events_count} initial timeline events.")
                
                conn.commit()
    except Exception as e:
        print(f"Fix failed: {e}")

if __name__ == "__main__":
    fix_legacy_timeline()
