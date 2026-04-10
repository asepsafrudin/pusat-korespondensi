#!/usr/bin/env python3
"""
Report PUU POSISI Mapping
=========================
Audit untuk memastikan kolom POSISI bisa dipetakan konsisten ke:
- timeline event
- status terakhir
- tanggal diterima PUU

Script ini hanya membaca data dan menulis laporan JSON opsional.

Jalankan:
  python3 scripts/report_puu_posisi_mapping.py
  python3 scripts/report_puu_posisi_mapping.py --limit 20
  python3 scripts/report_puu_posisi_mapping.py --unique-id 0327_000.4.2_834_bu_set
  python3 scripts/report_puu_posisi_mapping.py --json-out storage/admin_data/korespondensi/puu_posisi_mapping_audit.json
"""

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import psycopg

PROJECT_ROOT = "/home/aseps/MCP/mcp-unified"
sys.path.insert(0, PROJECT_ROOT)

from core.secrets import load_runtime_secrets  # type: ignore
from integrations.korespondensi.utils import (  # type: ignore
    parse_posisi_timeline,
    extract_puu_received_date,
    translate_disposisi,
)

load_runtime_secrets()

BULAN_ID = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}


def fmt_date(value):
    if value is None:
        return "-"
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return f"{value.day:02d} {BULAN_ID.get(value.month, '')} {value.year}"
    return str(value)


def fetch_rows(unique_id: str | None, limit: int):
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL belum diset")

    query = """
        SELECT
            unique_id,
            nomor_nd,
            posisi,
            tanggal_surat,
            tanggal_diterima_puu,
            agenda_puu,
            no_agenda_dispo,
            hal,
            dari
        FROM surat_masuk_puu_internal
    """
    params = []
    if unique_id:
        query += " WHERE unique_id = %s"
        params.append(unique_id)
    query += " ORDER BY tanggal_surat DESC, id DESC"
    if limit > 0:
        query += " LIMIT %s"
        params.append(limit)

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def build_report(row: dict) -> dict:
    posisi = row.get("posisi") or ""
    timeline = parse_posisi_timeline(posisi)
    pos_info = translate_disposisi(row.get("no_agenda_dispo") or "", sender=row.get("dari"))
    puu_date = extract_puu_received_date(posisi)

    missing = []
    if not row.get("agenda_puu"):
        missing.append("agenda_puu")
    if not row.get("no_agenda_dispo"):
        missing.append("no_agenda_dispo")
    if not row.get("tanggal_diterima_puu"):
        missing.append("tanggal_diterima_puu")

    return {
        "unique_id": row.get("unique_id"),
        "nomor_nd": row.get("nomor_nd"),
        "posisi": posisi,
        "agenda_puu": row.get("agenda_puu"),
        "no_agenda_dispo": row.get("no_agenda_dispo"),
        "tanggal_diterima_puu": fmt_date(row.get("tanggal_diterima_puu")),
        "puu_received_date_from_helper": puu_date,
        "timeline_count": len(timeline),
        "timeline_last_unit": timeline[-1]["unit"] if timeline else None,
        "timeline_last_date": timeline[-1]["date"] if timeline else None,
        "timeline_last_action": timeline[-1]["action"] if timeline else None,
        "is_surat_masuk_puu": pos_info.get("is_surat_masuk_puu", False),
        "mapping_status": "OK" if not missing else f"MISS: {', '.join(missing)}",
        "missing": missing,
    }


def audit_posisi_rows(unique_id: str | None = None, limit: int = 20) -> list[dict]:
    """Return structured audit rows for reuse inside ETL/workflow."""
    rows = fetch_rows(unique_id, limit)
    return [build_report(row) for row in rows]


def main():
    parser = argparse.ArgumentParser(description="Audit mapping POSISI untuk workflow PUU")
    parser.add_argument("--limit", type=int, default=20, help="Jumlah baris yang dicek")
    parser.add_argument("--unique-id", dest="unique_id", help="Cek satu baris spesifik")
    parser.add_argument("--json-out", dest="json_out", help="Simpan laporan JSON")
    args = parser.parse_args()

    reports = audit_posisi_rows(args.unique_id, args.limit)
    if not reports:
        print("Tidak ada data yang ditemukan.")
        return 0

    for report in reports:
        print(
            f"{report['unique_id']} | {report['mapping_status']} | "
            f"AGENDA={report['agenda_puu'] or '-'} | "
            f"TGL_PUU={report['tanggal_diterima_puu']} | "
            f"LAST={report['timeline_last_unit'] or '-'}:{report['timeline_last_action'] or '-'}@{report['timeline_last_date'] or '-'} | "
            f"POSISI={report['posisi'] or '-'}"
        )

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nLaporan JSON disimpan ke: {out_path}")

    issues = sum(1 for r in reports if r["missing"])
    print()
    print(f"Total rows checked: {len(reports)}")
    print(f"Rows with issues: {issues}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
