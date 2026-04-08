import os
import subprocess
import logging
from ..database import get_db_connection, execute_query
from ..logging_config import setup_logging

logger = setup_logging("sync_service")

# Constants from environment
SCRIPTS_DIR = os.getenv("PROJECT_SCRIPTS_DIR", "/home/aseps/MCP/scripts")
PYTHON_BIN = os.getenv("PYTHON_EXECUTABLE", "python3")
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
GDRIVE_TOKEN_PATH = os.getenv("GDRIVE_TOKEN_PATH")

def sync_internal_from_pool() -> int:
    """
    Ingest data from korespondensi_raw_pool to surat_masuk_puu_internal.
    Uses precise filters (keywords in posisi, disposisi, hal) and avoids duplicates via unique_id.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Deduplication Strategy: 'INT-' + id + '-' + sanitized agenda
                cur.execute("""
                    INSERT INTO surat_masuk_puu_internal 
                        (unique_id, tanggal_surat, nomor_nd, dari, hal, no_agenda_dispo, raw_pool_id, status_pengiriman, is_puu, agenda_puu, tanggal_diterima_puu)
                    SELECT 
                        'INT-' || id || '-' || COALESCE(REGEXP_REPLACE(no_agenda, '[^a-zA-Z0-9]', '', 'g'), 'NA'), 
                        tanggal, 
                        COALESCE(nomor_nd, 'NO-NUM'), 
                        COALESCE(dari, 'Unknown') || ' - ' || source_sheet_name, 
                        hal, 
                        COALESCE(SUBSTRING(disposisi FROM '(?i)\d{3,4}/.+/\d{4}'), no_agenda), 
                        id, 
                        'Belum Diproses', 
                        true,
                        LPAD((COALESCE((SELECT MAX(SPLIT_PART(agenda_puu, '-', 1)::INT) FROM surat_masuk_puu_internal), 0) + ROW_NUMBER() OVER(ORDER BY COALESCE(
                            CASE WHEN SUBSTRING(posisi FROM '(?i)(?:puu|hukum).*?(\d{1,2}/\d{1,2})') IS NOT NULL 
                                 THEN TO_DATE(SUBSTRING(posisi FROM '(?i)(?:puu|hukum).*?(\d{1,2}/\d{1,2})') || '/' || CASE WHEN SPLIT_PART(SUBSTRING(posisi FROM '(?i)(?:puu|hukum).*?(\d{1,2}/\d{1,2})'), '/', 2) = '12' THEN '2025' ELSE '2026' END, 'DD/MM/YYYY')
                                 ELSE NULL END,
                            tanggal) ASC, id ASC))::TEXT, 3, '0') || '-I',
                        CASE 
                            WHEN SUBSTRING(posisi FROM '(?i)(?:puu|hukum).*?(\d{1,2}/\d{1,2})') IS NOT NULL 
                            THEN TO_DATE(SUBSTRING(posisi FROM '(?i)(?:puu|hukum).*?(\d{1,2}/\d{1,2})') || '/' || CASE WHEN SPLIT_PART(SUBSTRING(posisi FROM '(?i)(?:puu|hukum).*?(\d{1,2}/\d{1,2})'), '/', 2) = '12' THEN '2025' ELSE '2026' END, 'DD/MM/YYYY')
                            ELSE NULL 
                        END
                    FROM korespondensi_raw_pool 
                    WHERE (
                        disposisi ~ '(?i)\d{3,4}/.+/\d{4}' AND 
                        posisi ~ '(?i)PUU.*?\d{1,2}/\d{1,2}'
                    )
                    AND id NOT IN (SELECT raw_pool_id FROM surat_masuk_puu_internal WHERE raw_pool_id IS NOT NULL)
                    ON CONFLICT (unique_id) DO NOTHING;
                """)
                rows_inserted = cur.rowcount
                conn.commit()
                return rows_inserted
    except Exception as e:
        logger.error(f"Sync internal failed: {e}")
        return -1

def trigger_etl_korespondensi() -> bool:
    """Trigger the main ETL script for pusat synchronization."""
    script_path = os.path.join(SCRIPTS_DIR, "etl_korespondensi_db_centric.py")
    try:
        # Run asynchronously in background, capture output to see why it fails
        log_file = open('/home/aseps/MCP/korespondensi-server/etl_background.log', 'w')
        # Inject explicit DATABASE_URL string locally to strictly fulfill the ETL's need if running in weird Popen scope
        env = os.environ.copy()
        
        subprocess.Popen(
            [PYTHON_BIN, script_path], 
            stdout=log_file, 
            stderr=subprocess.STDOUT,
            cwd="/home/aseps/MCP/korespondensi-server",
            env=env
        )
        return True
    except Exception as e:
        logger.error(f"Trigger ETL failed: {e}")
        return False

def get_stats():
    """Get dashboard summary statistics."""
    try:
        pool_count = execute_query("SELECT COUNT(*) as c FROM korespondensi_raw_pool")[0]['c']
        internal_count = execute_query("SELECT COUNT(*) as c FROM surat_masuk_puu_internal")[0]['c']
        substansi_count = execute_query("SELECT COUNT(*) as c FROM surat_untuk_substansi_puu")[0]['c']
        
        return {
            "pool": pool_count,
            "internal": internal_count,
            "substansi": substansi_count
        }
    except:
        return {"pool": 0, "internal": 0, "substansi": 0}

def upload_to_gdrive(file_path: str, unique_id: str):
    """Unggah file .docx hasil generate ke Google Drive di belakang layar dan simpan URL-nya."""
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import os
    import logging

    try:
        # Load local token explicitly to avoid MCP App Universal scopes requirement
        token_path = GDRIVE_TOKEN_PATH
        
        if not token_path or not os.path.exists(token_path):
            logger.error(f"[Google Drive Auto-Sync] Token tidak ditemukan atau belum dikonfigurasi.")
            return
            
        creds = Credentials.from_authorized_user_file(token_path)
        svc = build("drive", "v3", credentials=creds)
        
        filename = os.path.basename(file_path)
        # Folder ID dari environment
        folder_id = GDRIVE_FOLDER_ID
        
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        media = MediaFileUpload(
            file_path, 
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document', 
            resumable=True
        )
        
        # Minta 'id' dan 'webViewLink'
        result = svc.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id, webViewLink'
        ).execute()
        
        drive_id = result.get('id')
        drive_url = result.get('webViewLink')
        
        if drive_url and unique_id:
            execute_query(
                "UPDATE surat_masuk_puu_internal SET drive_file_url = %s WHERE unique_id = %s", 
                [drive_url, unique_id], 
                fetch=False
            )
            logger.info(f"[Google Drive Auto-Sync] Berhasil mengunggah dokumen: {filename} (Link: {drive_url})")
        
    except Exception as e:
        logger.error(f"[Google Drive Auto-Sync] Gagal mengunggah {file_path}: {e}")

def get_personnel_stats():
    """Menghitung jumlah dokumen per PIC dari tabel internal."""
    try:
        sql = """
            SELECT pic_name, COUNT(*) as count 
            FROM surat_masuk_puu_internal 
            WHERE pic_name IS NOT NULL AND pic_name != ''
            GROUP BY pic_name 
            ORDER BY count DESC 
            LIMIT 5
        """
        return execute_query(sql)
    except Exception as e:
        logger.error(f"Failed to get personnel stats: {e}")
        return []

def get_letter_timeline(unique_id: str):
    """Mengambil riwayat perjalanan (timeline) posisi surat."""
    try:
        sql = """
            SELECT ce.event_value as posisi, ce.event_at, ce.created_at 
            FROM correspondence_events ce
            JOIN surat_masuk_puu_internal s ON s.id = ce.letter_id
            WHERE s.unique_id = %s
            ORDER BY ce.event_at ASC
        """
        return execute_query(sql, [unique_id])
    except Exception as e:
        logger.error(f"Failed to get timeline for {unique_id}: {e}")
        return []
