import re
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

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

_POSITION_DICT_CANDIDATES = [
    Path("/home/aseps/MCP/knowledge/korespondensi_posisi_dictionary_minimal_2026-04-09.json"),
    Path(__file__).resolve().parents[3] / "knowledge" / "korespondensi_posisi_dictionary_minimal_2026-04-09.json",
]


@lru_cache(maxsize=1)
def _load_posisi_dictionary() -> Dict[str, Dict[str, str]]:
    dictionary: Dict[str, Dict[str, str]] = {}
    for candidate in _POSITION_DICT_CANDIDATES:
        try:
            if not candidate.exists():
                continue
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            for entry in payload.get("entries", []):
                token = str(entry.get("token") or "").strip().upper()
                if token:
                    dictionary[token] = {
                        "meaning": str(entry.get("meaning") or token),
                        "category": str(entry.get("category") or "misc"),
                    }
            if dictionary:
                break
        except Exception:
            continue
    return dictionary


def translate_posisi_token(token: Optional[str]) -> Dict[str, str]:
    token_upper = str(token or "").strip().upper()
    if not token_upper:
        return {"token": "", "meaning": "", "category": "misc"}
    dictionary = _load_posisi_dictionary()
    return {
        "token": token_upper,
        "meaning": dictionary.get(token_upper, {}).get("meaning", token_upper),
        "category": dictionary.get(token_upper, {}).get("category", "misc"),
    }


def format_short_date_id(date_str: Optional[str]) -> str:
    """
    Ubah tanggal ringkas `D/M` atau `DD/MM` menjadi bentuk Indonesia yang mudah dibaca.

    Contoh:
    - `16/3` -> `16 Maret`
    - `6/4` -> `6 April`

    Jika format tidak dikenali, fungsi mengembalikan nilai asli agar data tetap aman
    dan mudah ditelusuri saat debug.
    """
    if not date_str:
        return ""

    match = re.match(r"^(\d{1,2})/(\d{1,2})$", str(date_str).strip())
    if not match:
        return str(date_str)

    day = int(match.group(1))
    month = int(match.group(2))
    month_name = BULAN_ID.get(month)
    if not month_name:
        return str(date_str)
    return f"{day} {month_name}"


def parse_posisi_timeline(posisi_str: str, sender: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Parse POSISI menjadi timeline terstruktur.
    Versi lokal untuk workflow korespondensi-server.
    """
    if not posisi_str or str(posisi_str).upper() == "NULL":
        return []

    units = ["SES", "TU", "BU", "KEU", "PRC", "PUU", "PEIPD", "SUPD", "SD", "DIRJEN", "DITJEN", "BANGDA", "UMUM"]
    actions = ["KOREKSI", "REVISI", "TTD", "PARAFA", "PARAF", "ST", "SISTEM", "BAGI", "DITERIMA", "DONE", "SELESAI", "PROSES", "DJ"]
    systems = ["SRIKANDI", "SIMND", "POOLING"]

    multi_unit_pattern = re.compile(r'^([A-Za-z]+(?:\s*,\s*[A-Za-z]+)+)\s+(\d{1,2}/\d{1,2})$')
    multi_match = multi_unit_pattern.match(posisi_str.strip())
    if multi_match:
        units_part = multi_match.group(1)
        shared_date = multi_match.group(2)
        unit_names = [u.strip().upper() for u in units_part.split(',')]
        return [{"unit": u if u in units else u, "date": shared_date, "action": "DISPOSISI", "notes": f"Multi-unit batch: {units_part}"} for u in unit_names]

    pattern = re.compile(r'(\d{1,2}/\d{1,2})|(\d{1,2}\.?\d{2}\.?\d{0,2})|(\([^\)]+\))|([a-zA-Z\d\.\-]+)', re.IGNORECASE)
    tokens = [m.groups() for m in pattern.finditer(posisi_str)]
    timeline: List[Dict[str, Any]] = []
    current_unit = "UNKNOWN"
    current_date = None

    for date_val, time_val, bracket_val, word_val in tokens:
        if date_val:
            current_date = date_val
            if timeline and timeline[-1].get("date") is None:
                timeline[-1]["date"] = current_date
                continue
            elif not timeline or timeline[-1]["date"] != current_date:
                timeline.append({"unit": current_unit, "date": current_date, "action": "UPDATE", "notes": ""})
            continue
        if time_val:
            clean_time = str(time_val).replace(".", ":")
            if clean_time.count(":") > 1:
                clean_time = ":".join(clean_time.split(":")[:2])
            if timeline:
                timeline[-1]["time"] = clean_time
            continue
        if bracket_val:
            notes = bracket_val.strip("()")
            if timeline:
                timeline[-1]["notes"] = (timeline[-1].get("notes", "") + " " + notes).strip()
            continue
        if word_val:
            word_upper = word_val.upper()
            if any(u == word_upper for u in units):
                current_unit = word_upper
                timeline.append({"unit": current_unit, "date": current_date, "action": "POSITION_CHECK", "notes": ""})
                continue
            if any(a in word_upper for a in actions):
                action = "KOREKSI (oleh %s)" % sender if "KOREKSI" in word_upper and sender else word_upper
                if timeline:
                    last = timeline[-1]
                    if last["unit"] == current_unit and last["date"] == current_date:
                        if last["action"] in ["UPDATE", "POSITION_CHECK"]:
                            last["action"] = action
                        else:
                            last["action"] += f"+{action}"
                    else:
                        timeline.append({"unit": current_unit, "date": current_date, "action": action, "notes": ""})
                else:
                    timeline.append({"unit": current_unit, "date": current_date, "action": action, "notes": ""})
                continue
            if word_upper in systems and timeline:
                timeline[-1]["action"] += f" (via {word_val})"

    merged: List[Dict[str, Any]] = []
    for ev in timeline:
        if not merged:
            merged.append(ev)
            continue
        last = merged[-1]
        if ev["unit"] == last["unit"] and ev["date"] == last["date"]:
            if ev["action"] not in ["UPDATE", "POSITION_CHECK"]:
                last["action"] = ev["action"]
            if ev.get("notes"):
                last["notes"] = (last.get("notes", "") + " " + ev["notes"]).strip()
            if ev.get("time"):
                last["time"] = ev["time"]
        else:
            merged.append(ev)
    return merged


def format_posisi_event(event: Dict[str, Any]) -> str:
    unit = event.get("unit") or "UNKNOWN"
    date = format_short_date_id(event.get("date"))
    action = event.get("action") or "UPDATE"
    action_map = {
        "UPDATE": "Update",
        "POSITION_CHECK": "Posisi diterima",
        "DISPOSISI": "Disposisi",
    }
    readable_action = action_map.get(action, action.replace("_", " ").title())
    if unit == "UNKNOWN" and readable_action == "Update":
        readable_action = "Update timeline"
    unit_info = translate_posisi_token(unit)
    unit_label = unit_info["meaning"] or unit
    label = f"{unit_label} {date}" if date else unit_label
    return f"{label} - {readable_action}"


def build_posisi_timeline_view(posisi_str: str, sender: Optional[str] = None) -> List[Dict[str, Any]]:
    timeline = parse_posisi_timeline(posisi_str, sender=sender)
    view = []
    for event in timeline:
        item = dict(event)
        item["unit_info"] = translate_posisi_token(event.get("unit"))
        item["label"] = format_posisi_event(event)
        view.append(item)
    return view
