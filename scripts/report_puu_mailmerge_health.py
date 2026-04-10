#!/usr/bin/env python3
"""
Report PUU Mailmerge Health
===========================
Audit ringan untuk memastikan field yang dipakai mailmerge PUU terisi:
- agenda_puu
- no_agenda_dispo
- tanggal_diterima_puu

Script ini tidak mengubah data. Tujuannya untuk verifikasi cepat sebelum
generate DOCX dan untuk memudahkan investigasi jika hasil mailmerge tidak lengkap.

Jalankan:
  python3 scripts/report_puu_mailmerge_health.py
  python3 scripts/report_puu_mailmerge_health.py --limit 20
  python3 scripts/report_puu_mailmerge_health.py --unique-id 0327_000.4.2_834_bu_set
"""

import argparse
import os
import sys
from datetime import date, datetime

import psycopg

PROJECT_ROOT = "/home/aseps/MCP/mcp-unified"
sys.path.insert(0, PROJECT_ROOT)

from core.secrets import load_runtime_secrets  # type: ignore

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
            no_agenda_dispo,
            agenda_puu,
            tanggal_diterima_puu,
            posisi,
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


def main():
    parser = argparse.ArgumentParser(description="Audit field mailmerge PUU")
    parser.add_argument("--limit", type=int, default=20, help="Jumlah baris yang dicek")
    parser.add_argument("--unique-id", dest="unique_id", help="Cek satu baris spesifik")
    args = parser.parse_args()

    rows = fetch_rows(args.unique_id, args.limit)
    if not rows:
        print("Tidak ada data yang ditemukan.")
        return 0

    issues = []
    for row in rows:
        missing = []
        if not row.get("no_agenda_dispo"):
            missing.append("no_agenda_dispo")
        if not row.get("agenda_puu"):
            missing.append("agenda_puu")
        if not row.get("tanggal_diterima_puu"):
            missing.append("tanggal_diterima_puu")

        status = "OK" if not missing else f"MISS: {', '.join(missing)}"
        print(
            f"{row['unique_id']} | {status} | "
            f"ND={row.get('nomor_nd') or '-'} | "
            f"DISPO={row.get('no_agenda_dispo') or '-'} | "
            f"AGENDA_PUU={row.get('agenda_puu') or '-'} | "
            f"TGL_DITERIMA={fmt_date(row.get('tanggal_diterima_puu'))} | "
            f"POSISI={row.get('posisi') or '-'}"
        )
        if missing:
            issues.append((row["unique_id"], missing))

    print()
    print(f"Total rows checked: {len(rows)}")
    print(f"Rows with issues: {len(issues)}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
