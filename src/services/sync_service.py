import os
import subprocess
import logging
from ..database import get_db_connection, execute_query
from ..logging_config import setup_logging
from .posisi_mapping import build_posisi_timeline_view
from .personnel import get_unit_mapping

import re
from datetime import datetime, date

_DARI_FALLBACK = {
    "BU": "Bagian Umum", "UM": "Bagian Umum", "TU": "Tata Usaha",
    "KEU": "Bagian Keuangan", "PRC": "Bagian Perencanaan",
}

def map_dari_full(dari_code: str) -> str:
    """Helper to map DARI code to full name."""
    if not dari_code: return ""
    norm = re.sub(r'[\s\.]+', ' ', dari_code.strip().upper()).strip()
    # Handle combined strings like "KEU - SEKRETARIAT"
    parts = norm.split('-')
    core_code = parts[0].strip()
    source_sheet = parts[1].strip() if len(parts) > 1 else ""
    
    full_name = get_unit_mapping().get(core_code)
    if not full_name:
        full_name = _DARI_FALLBACK.get(core_code, core_code)
    return f"{full_name} - {source_sheet}" if source_sheet else full_name

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
                # Synchronize data and log initial timeline events via CTE
                cur.execute("""
                    WITH inserted_letters AS (
                        INSERT INTO surat_masuk_puu_internal 
                            (unique_id, tanggal_surat, nomor_nd, dari, hal, no_agenda_dispo, raw_pool_id, status_pengiriman, is_puu, agenda_puu, tanggal_diterima_puu, posisi)
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
                            END,
                            posisi
                        FROM korespondensi_raw_pool 
                        WHERE (
                            disposisi ~ '(?i)\d{3,4}/.+/\d{4}' AND 
                            posisi ~ '(?i)PUU.*?\d{1,2}/\d{1,2}'
                        )
                        AND id NOT IN (SELECT raw_pool_id FROM surat_masuk_puu_internal WHERE raw_pool_id IS NOT NULL)
                        ON CONFLICT (unique_id) DO NOTHING
                        RETURNING id, posisi, tanggal_diterima_puu
                    )
                    INSERT INTO correspondence_events (letter_id, event_type, event_value, event_at)
                    SELECT id, 'posisi_change', posisi, COALESCE(tanggal_diterima_puu, NOW())
                    FROM inserted_letters;
                """)
                rows_inserted = cur.rowcount
                
                # Post-sync: Update dari_full and normalize dari combination
                if rows_inserted > 0:
                    cur.execute("SELECT id, dari FROM surat_masuk_puu_internal WHERE dari_full IS NULL OR dari_full = ''")
                    new_rows = cur.fetchall()
                    for r in new_rows:
                        full_name = map_dari_full(r[1])
                        if full_name != r[1]:
                            cur.execute("UPDATE surat_masuk_puu_internal SET dari_full = %s WHERE id = %s", [full_name, r[0]])
                
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
        pool_res = execute_query("SELECT COUNT(*) as c FROM korespondensi_raw_pool")
        pool_count = pool_res[0]['c'] if pool_res else 0
        
        internal_res = execute_query("SELECT COUNT(*) as c FROM surat_masuk_puu_internal")
        internal_count = internal_res[0]['c'] if internal_res else 0
        
        substansi_res = execute_query("SELECT COUNT(*) as c FROM surat_untuk_substansi_puu")
        substansi_count = substansi_res[0]['c'] if substansi_res else 0
        
        staff_res = execute_query("SELECT COUNT(*) as c FROM staff_details")
        staff_count = staff_res[0]['c'] if staff_res else 0
        
        return {
            "pool": pool_count,
            "internal": internal_count,
            "substansi": substansi_count,
            "staff": staff_count
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {"pool": 0, "internal": 0, "substansi": 0}

def upload_to_gdrive(file_path: str, unique_id: str):
    """Unggah file .docx hasil generate ke Google Drive di belakang layar dan simpan URL-nya."""
    from googleapiclient.http import MediaFileUpload
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    import os
    import json
    import logging

    try:
        token_path = GDRIVE_TOKEN_PATH
        if not token_path or not os.path.exists(token_path):
            logger.error(f"[Google Drive Auto-Sync] Kredential tidak ditemukan.")
            return None
            
        # Detect credential type
        with open(token_path, 'r') as f:
            creds_data = json.load(f)
            
        if creds_data.get('type') == 'service_account':
            creds = service_account.Credentials.from_service_account_file(
                token_path, 
                scopes=["https://www.googleapis.com/auth/drive.file"]
            )
        else:
            from google.oauth2.credentials import Credentials
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
            return drive_url
        
        return None
        
    except Exception as e:
        logger.error(f"[Google Drive Auto-Sync] Gagal mengunggah {file_path}: {e}")
        return None

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
        res = execute_query(sql)
        return res if res else []
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
        rows = execute_query(sql, [unique_id])
        events = []
        for row in (rows or []):
            posisi = row.get("posisi") or ""
            timeline_view = build_posisi_timeline_view(posisi)
            if timeline_view:
                for idx, item in enumerate(timeline_view):
                    events.append({
                        "posisi": item.get("label") or posisi,
                        "posisi_raw": posisi,
                        "label": item.get("label") or posisi,
                        "event_at": row.get("event_at"),
                        "created_at": row.get("created_at"),
                        "timeline_unit": item.get("unit"),
                        "timeline_date": item.get("date"),
                        "timeline_action": item.get("action"),
                        "timeline_notes": item.get("notes"),
                        "timeline_index": idx,
                    })
            else:
                events.append({
                    "posisi": posisi,
                    "posisi_raw": posisi,
                    "label": posisi,
                    "event_at": row.get("event_at"),
                    "created_at": row.get("created_at"),
                    "timeline_unit": None,
                    "timeline_date": None,
                    "timeline_action": None,
                    "timeline_notes": None,
                    "timeline_index": 0,
                })
        return events
    except Exception as e:
        logger.error(f"Failed to get timeline for {unique_id}: {e}")
        return []
