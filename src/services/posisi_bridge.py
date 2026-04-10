import re
from typing import Any, Dict, List, Optional

from ..database import execute_query
from .posisi_mapping import build_posisi_timeline_view


def _normalize_search_term(value: str) -> str:
    return value.strip().replace(".", "%").replace(" ", "%")


def _extract_posisi_terms(posisi_raw: str) -> List[str]:
    """
    Extract normalized dictionary candidates from raw POSISI text.

    Rules:
    - Keep uppercase tokens
    - Keep code-like tokens containing dots or digits (e.g. SD.1, 17/3)
    - Remove very short noise tokens
    - Preserve organization codes and action words as separate entries
    """
    if not posisi_raw:
        return []

    normalized = (
        str(posisi_raw)
        .replace(",", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("-", " ")
        .replace(":", " ")
    )
    tokens = re.findall(r"[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*", normalized)
    terms: List[str] = []
    for token in tokens:
        cleaned = token.strip().upper()
        if len(cleaned) < 2:
            continue
        if cleaned in {"DI", "KE", "KEPADA", "DARI", "DAN", "ATAU"}:
            continue
        terms.append(cleaned)
    return terms


def get_unique_posisi_mappings(limit: int = 200, q: str = "") -> List[Dict[str, Any]]:
    """
    Read-only bridge for distinct POSISI values.

    The goal is to expose unique raw POSISI strings together with the parsed
    timeline view so sandboxed agents and other IDE runtimes can inspect the
    mapping without connecting to PostgreSQL directly.
    """
    sql = """
        SELECT posisi, COUNT(*) AS posisi_count
        FROM korespondensi_raw_pool
        WHERE posisi IS NOT NULL
          AND TRIM(posisi) <> ''
    """
    params: List[Any] = []

    if q:
        robust_q = _normalize_search_term(q)
        sql += " AND posisi ILIKE %s"
        params.append(f"%{robust_q}%")

    sql += " GROUP BY posisi ORDER BY posisi ASC LIMIT %s"
    params.append(limit)

    rows = execute_query(sql, params)
    result: List[Dict[str, Any]] = []

    for row in rows:
        posisi_raw = row.get("posisi") or ""
        result.append(
            {
                "posisi_raw": posisi_raw,
                "count": int(row.get("posisi_count") or 0),
                "timeline": build_posisi_timeline_view(posisi_raw),
            }
        )

    return result


def get_unique_posisi_by_sheet(limit_per_sheet: int = 100, q: str = "") -> List[Dict[str, Any]]:
    """
    Group unique POSISI values per spreadsheet/sheet source.

    This is useful when the same POSISI pattern appears in multiple sheets and
    we want to understand the mapping in its native source context.
    """
    sheet_sql = """
        SELECT DISTINCT source_spreadsheet_id, source_sheet_name
        FROM korespondensi_raw_pool
        WHERE source_spreadsheet_id IS NOT NULL
          AND TRIM(source_spreadsheet_id) <> ''
          AND source_sheet_name IS NOT NULL
          AND TRIM(source_sheet_name) <> ''
        ORDER BY source_sheet_name ASC, source_spreadsheet_id ASC
    """
    sheet_rows = execute_query(sheet_sql)
    payload: List[Dict[str, Any]] = []

    for sheet in sheet_rows:
        source_spreadsheet_id = sheet.get("source_spreadsheet_id") or ""
        source_sheet_name = sheet.get("source_sheet_name") or ""

        sql = """
            SELECT posisi, COUNT(*) AS posisi_count
            FROM korespondensi_raw_pool
            WHERE source_spreadsheet_id = %s
              AND source_sheet_name = %s
              AND posisi IS NOT NULL
              AND TRIM(posisi) <> ''
        """
        params: List[Any] = [source_spreadsheet_id, source_sheet_name]

        if q:
            robust_q = _normalize_search_term(q)
            sql += " AND posisi ILIKE %s"
            params.append(f"%{robust_q}%")

        sql += " GROUP BY posisi ORDER BY posisi ASC LIMIT %s"
        params.append(limit_per_sheet)

        rows = execute_query(sql, params)
        items: List[Dict[str, Any]] = []
        for row in rows:
            posisi_raw = row.get("posisi") or ""
            items.append(
                {
                    "posisi_raw": posisi_raw,
                    "count": int(row.get("posisi_count") or 0),
                    "timeline": build_posisi_timeline_view(posisi_raw),
                }
            )

        payload.append(
            {
                "source_spreadsheet_id": source_spreadsheet_id,
                "source_sheet_name": source_sheet_name,
                "count": len(items),
                "data": items,
            }
        )

    return payload


def get_unique_posisi_terms(limit: int = 500, q: str = "") -> List[Dict[str, Any]]:
    """
    Build a unique token list from POSISI values across all sheets.

    This is intended as the starting point for a human-readable dictionary.
    """
    sql = """
        SELECT posisi, source_sheet_name, source_spreadsheet_id
        FROM korespondensi_raw_pool
        WHERE posisi IS NOT NULL
          AND TRIM(posisi) <> ''
        ORDER BY source_sheet_name ASC, posisi ASC
    """
    rows = execute_query(sql)
    term_map: Dict[str, Dict[str, Any]] = {}

    q_upper = q.strip().upper()
    for row in rows:
        posisi_raw = row.get("posisi") or ""
        source_sheet_name = row.get("source_sheet_name") or ""
        source_spreadsheet_id = row.get("source_spreadsheet_id") or ""

        for term in _extract_posisi_terms(posisi_raw):
            if q_upper and q_upper not in term:
                continue

            entry = term_map.setdefault(
                term,
                {
                    "term": term,
                    "count": 0,
                    "sheets": set(),
                    "examples": [],
                },
            )
            entry["count"] += 1
            entry["sheets"].add(f"{source_sheet_name} ({source_spreadsheet_id})")
            if len(entry["examples"]) < 3 and posisi_raw not in entry["examples"]:
                entry["examples"].append(posisi_raw)

    items: List[Dict[str, Any]] = []
    for term, entry in term_map.items():
        items.append(
            {
                "term": term,
                "count": entry["count"],
                "sheets": sorted(entry["sheets"]),
                "examples": entry["examples"],
            }
        )

    items.sort(key=lambda x: (-x["count"], x["term"]))
    return items[: max(1, min(limit, 2000))]
