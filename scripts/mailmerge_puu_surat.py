#!/usr/bin/env python3
"""
Mailmerge: Generate Surat dari Template Google Docs untuk Substansi PUU
========================================================================
Mengambil data dari `surat_untuk_substansi_puu` dan generate dokumen
dari template Google Docs.

Template ID: 1lQH-NMy1pU9Cw-iTsR9pDLex6kc9NeJALIG3I7uvWEI
Target Folder: 1v5OjzdXBc9xX95FcRBopT6seze_p0H8Q

Jalankan:
  python3 scripts/mailmerge_puu_surat.py
  python3 scripts/mailmerge_puu_surat.py --limit 5
  python3 scripts/mailmerge_puu_surat.py --dry-run
"""
import os
import sys
import json
import logging
import argparse
from datetime import datetime, date

PROJECT_ROOT = "/home/aseps/MCP/mcp-unified"
sys.path.insert(0, PROJECT_ROOT)
from core.secrets import load_runtime_secrets
load_runtime_secrets()

import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mailmerge_puu")

TEMPLATE_ID = "1lQH-NMy1pU9Cw-iTsR9pDLex6kc9NeJALIG3I7uvWEI"
FOLDER_ID = "1v5OjzdXBc9xX95FcRBopT6seze_p0H8Q"

# Placeholder mapping dari template ke kolom database
# Catatan: 
#   - <<Agenda PUU>> diisi otomatis dengan sequence XXX/L mulai dari 001/L
#   - <<Tgl Diterima PUU>> dikosongkan (diisi manual oleh admin PUU)
PLACEHOLDER_MAP = {
    "<<Surat Dari>>": "surat_dari",
    "<<Nomor Surat>>": "nomor_surat",
    "<<Tgl Surat>>": "tgl_surat",
    "<<Tgl Diterima PUU>>": "",  # Kosong - diisi manual admin PUU
    "<<No Agenda Ses>>": "no_agenda_ses",
    "<<Agenda PUU>>": "agenda_puu",  # Auto-generated: 001/L, 002/L, ...
    "<<Perihal>>": "perihal",
}

# Kolom tanggal yang perlu diformat
DATE_COLUMNS = ["tgl_surat"]

BULAN_ID = {1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
            7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"}

def fmt_date(d):
    """Format tanggal Indonesia."""
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d.replace('Z', '+00:00'))
        except:
            return d
    if isinstance(d, (datetime, date)):
        return f"{d.day} {BULAN_ID.get(d.month, '')} {d.year}"
    return d or "-"

def get_services():
    """Get Docs & Drive services."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request

    token_path = "/home/aseps/MCP/config/credentials/google/puubangda/token.json"
    secret_path = "/home/aseps/MCP/config/credentials/google/puubangda/client_secret.json"

    with open(token_path) as f:
        tok = json.load(f)
    with open(secret_path) as f:
        cs = json.load(f)
    web = cs.get("web") or cs.get("installed", {})

    creds = Credentials(
        token=tok.get("token"), refresh_token=tok.get("refresh_token"),
        token_uri=tok.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=web.get("client_id", tok.get("client_id")),
        client_secret=web.get("client_secret", tok.get("client_secret")),
        scopes=tok.get("scopes", []))
    if creds.expired and creds.refresh_token:
        log.info("Refreshing token...")
        creds.refresh(Request())
        with open(token_path, "w") as f:
            json.dump({**tok, "token": creds.token}, f, indent=2)

    return build("docs", "v1", credentials=creds), build("drive", "v3", credentials=creds)

def get_surat_puu_data(limit=0):
    """Get data dari tabel surat_untuk_substansi_puu JOIN surat_dari_luar_bangda.
    
    Catatan:
    - agenda_puu diisi otomatis dengan sequence 001/L, 002/L, dst
    - tgl_diterima_ula TIDAK diambil (diisi manual admin PUU)
    """
    dsn = os.getenv("DATABASE_URL")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            query = """
                SELECT 
                    sp.id,
                    sp.surat_id,
                    sp.agenda,
                    sp.surat_dari,
                    sp.nomor_surat,
                    sdlb.perihal,
                    sp.disposisi_kepada,
                    sp.isi_disposisi,
                    sp.tanggal_disposisi,
                    sp.status,
                    sdlb.tgl_surat,
                    sp.no_agenda_ses
                FROM surat_untuk_substansi_puu sp
                JOIN surat_dari_luar_bangda sdlb ON sdlb.id = sp.surat_id
                ORDER BY sp.id
            """
            if limit > 0:
                query += f" LIMIT {limit}"
            cur.execute(query)
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            
            # Assign auto-generated agenda_puu sequence (001-L, 002-L, ...)
            # Format different from agenda ULA (001/L) to avoid confusion
            for i, row in enumerate(rows, 1):
                row["agenda_puu"] = f"{i:03d}-L"
            
            return rows

def fill_template(docs_svc, data: dict) -> str:
    """
    Fill template dengan data dan return document ID baru.
    Menggunakan batchUpdate untuk replace text.
    """
    # 1. Copy template
    from googleapiclient.discovery import build

    # Use drive_svc via global
    drive_svc = globals()['_drive_svc']
    template_name = f"Disposisi - {data['agenda_puu']}"
    
    copy_meta = {
        'name': template_name,
        'parents': [FOLDER_ID]
    }
    
    copied = drive_svc.files().copy(
        fileId=TEMPLATE_ID, body=copy_meta
    ).execute()
    new_doc_id = copied['id']
    log.info(f"Created doc: {new_doc_id} -> {template_name}")
    
    # 2. Prepare replacements
    requests = []
    for placeholder, col_name in PLACEHOLDER_MAP.items():
        value = data.get(col_name, "")
        if col_name in DATE_COLUMNS:
            value = fmt_date(value)
        
        requests.append({
            'replaceAllText': {
                'replaceText': str(value) if value else "-",
                'containsText': {
                    'text': placeholder,
                    'matchCase': True
                }
            }
        })
    
    # 3. Execute replacements
    if requests:
        docs_svc.documents().batchUpdate(
            documentId=new_doc_id,
            body={'requests': requests}
        ).execute()
        log.info(f"Filled {len(requests)} placeholders")
    
    return new_doc_id

def run(limit=0, dry_run=False):
    docs_svc, drive_svc = get_services()
    globals()['_drive_svc'] = drive_svc

    data_list = get_surat_puu_data(limit)
    if not data_list:
        log.info("No data found")
        return

    log.info(f"Found {len(data_list)} records to process")
    
    if dry_run:
        log.info("[DRY RUN] Would process:")
        for d in data_list[:5]:
            log.info(f"  {d['agenda']} | {d['surat_dari']} | {d['perihal'][:50]}")
        return

    results = []
    for data in data_list:
        try:
            new_doc_id = fill_template(docs_svc, data)
            doc_url = f"https://docs.google.com/document/d/{new_doc_id}/edit"
            
            # Save into DB
            dsn = os.getenv("DATABASE_URL")
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE surat_untuk_substansi_puu SET doc_url = %s, updated_at = NOW() WHERE id = %s",
                        (doc_url, data["id"])
                    )
                conn.commit()

            results.append({
                "agenda": data["agenda"],
                "surat_dari": data["surat_dari"],
                "doc_id": new_doc_id,
                "doc_url": doc_url,
                "status": "created"
            })
            log.info(f"OK: {data['agenda']} -> {new_doc_id}")
        except Exception as e:
            log.error(f"FAIL {data.get('agenda', '?')}: {e}")
            results.append({
                "agenda": data.get("agenda", "?"),
                "status": f"error: {e}"
            })

    print(json.dumps({"total": len(data_list), "results": results}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(limit=args.limit, dry_run=args.dry_run)