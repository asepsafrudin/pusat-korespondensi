from __future__ import annotations

import json
import os
import uuid
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from ..database import execute_query
from ..logging_config import setup_logging

logger = setup_logging("anomaly_report_service")

MCP_UNIFIED_ROOT = Path(os.getenv("MCP_UNIFIED_ROOT", "/home/aseps/MCP/mcp-unified"))
if str(MCP_UNIFIED_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_UNIFIED_ROOT))

try:
    from integrations.whatsapp.client import get_whatsapp_client
except Exception:  # pragma: no cover
    get_whatsapp_client = None

LOG_DIR = Path(os.getenv("KORESPONDESI_LOG_DIR", "/home/aseps/MCP/korespondensi-server/logs"))
LOG_FILE = Path(os.getenv("ANOMALY_REPORT_LOG_FILE", str(LOG_DIR / "anomaly_reports.jsonl")))
WAHA_API_URL = os.getenv("WHATSAPP_API_URL", "http://localhost:3001")
WAHA_API_KEY = os.getenv("WHATSAPP_API_KEY")
WAHA_API_AUTH_MODE = os.getenv("WHATSAPP_API_AUTH_MODE", "auto").strip().lower()
WAHA_SESSION = os.getenv("WHATSAPP_SESSION", "default")
WAHA_RECIPIENT = os.getenv("WHATSAPP_RECIPIENT", "")


@dataclass
class AnomalyReport:
    recipient_name: str
    recipient_phone: str
    finding_title: str
    finding_summary: str
    record_key: str = ""
    source_label: str = ""
    source_ref: str = ""
    impact: str = ""
    recommendation: str = ""
    reporter_name: str = "MCP Unified"
    reporter_role: str = "agent"
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_message(self) -> str:
        parts = [
            f"Assalamu’alaikum {self.recipient_name},",
            "",
            f"Saya dari {self.reporter_name} ingin melaporkan temuan anomali data yang perlu dicek lebih lanjut.",
            "",
            "Temuan:",
            self.finding_title,
            "",
            "Ringkasan:",
            self.finding_summary.strip(),
        ]

        if self.record_key:
            parts.extend(["", f"Kunci Data: {self.record_key}"])
        if self.source_label:
            parts.extend(["", f"Sumber: {self.source_label}"])
        if self.source_ref:
            parts.extend(["", f"Referensi: {self.source_ref}"])
        if self.impact:
            parts.extend(["", f"Dampak: {self.impact}"])
        if self.recommendation:
            parts.extend(["", f"Rekomendasi: {self.recommendation}"])

        parts.extend(
            [
                "",
                "Jika berkenan, mohon arahan apakah data ini perlu dikoreksi di sumber atau cukup difilter di tampilan.",
                "",
                "Terima kasih.",
                "Wassalamu’alaikum.",
            ]
        )
        return "\n".join(parts)


def ensure_log_dir() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def append_history(record: Dict[str, Any]) -> Path:
    ensure_log_dir()
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return LOG_FILE


def build_report(**kwargs: Any) -> AnomalyReport:
    return AnomalyReport(**kwargs)


def _report_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {
        "recipient_name",
        "recipient_phone",
        "finding_title",
        "finding_summary",
        "record_key",
        "source_label",
        "source_ref",
        "impact",
        "recommendation",
        "reporter_name",
        "reporter_role",
    }
    return {k: v for k, v in payload.items() if k in allowed and v is not None}


def normalize_chat_id(phone: str) -> str:
    chat_id = phone.strip()
    if not chat_id.endswith("@c.us") and not chat_id.endswith("@g.us"):
        chat_id = f"{chat_id}@c.us"
    return chat_id


async def send_to_whatsapp(message: str, recipient_phone: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    recipient_phone = recipient_phone or WAHA_RECIPIENT
    if not recipient_phone:
        return {"success": False, "error": "recipient_missing"}

    chat_id = normalize_chat_id(recipient_phone)
    url = f"{WAHA_API_URL}/api/sendText"
    payload = {
        "session": WAHA_SESSION,
        "chatId": chat_id,
        "text": message,
    }

    try:
        if get_whatsapp_client is not None:
            client = get_whatsapp_client()
            try:
                response = await client.send_message(
                    chat_id=chat_id,
                    text=message,
                    session_name=WAHA_SESSION,
                )
                ok = True
                result = {
                    "success": True,
                    "status_code": 200,
                    "response_text": json.dumps(response, ensure_ascii=False),
                    "chat_id": chat_id,
                    "used_api_key": bool(WAHA_API_KEY),
                    "auth_mode": "mcp_unified_client",
                }
                append_history(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "channel": "whatsapp",
                        "session": WAHA_SESSION,
                        "recipient_phone": recipient_phone,
                        "chat_id": chat_id,
                        "message": message,
                        "metadata": metadata or {},
                        "status": "sent",
                        "http_status": 200,
                        "used_api_key": bool(WAHA_API_KEY),
                        "auth_mode": "mcp_unified_client",
                    }
                )
                return result
            except Exception as shared_exc:
                logger.warning(f"Shared WhatsApp client failed, falling back to direct HTTP: {shared_exc}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            attempts = []
            if WAHA_API_AUTH_MODE in {"auto", "key"} and WAHA_API_KEY:
                attempts.append({"headers": {"X-Api-Key": WAHA_API_KEY}})
            if WAHA_API_AUTH_MODE in {"auto", "none"}:
                attempts.append({"headers": {}})
            if not attempts:
                attempts.append({"headers": {}})
            last_response = None
            last_error = None

            for attempt in attempts:
                try:
                    response = await client.post(url, json=payload, headers=attempt["headers"])
                    last_response = response
                    if response.status_code in (200, 201):
                        ok = True
                        break
                    if response.status_code != 401 or attempt["headers"] == {}:
                        ok = False
                        break
                except Exception as exc:
                    last_error = exc
                    if attempt["headers"] == {}:
                        raise
            else:
                ok = False

            if last_response is None and last_error is not None:
                raise last_error

            result = {
                "success": ok,
                "status_code": last_response.status_code if last_response else None,
                "response_text": last_response.text if last_response else "",
                "chat_id": chat_id,
                "used_api_key": bool(WAHA_API_KEY),
                "auth_mode": WAHA_API_AUTH_MODE,
            }
            append_history(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "channel": "whatsapp",
                    "session": WAHA_SESSION,
                    "recipient_phone": recipient_phone,
                    "chat_id": chat_id,
                    "message": message,
                    "metadata": metadata or {},
                    "status": "sent" if ok else "failed",
                    "http_status": last_response.status_code if last_response else None,
                    "used_api_key": bool(WAHA_API_KEY),
                    "auth_mode": WAHA_API_AUTH_MODE,
                }
            )
            return result
    except Exception as exc:
        append_history(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "channel": "whatsapp",
                "session": WAHA_SESSION,
                "recipient_phone": recipient_phone,
                "chat_id": chat_id,
                "message": message,
                "metadata": metadata or {},
                "status": "exception",
                "error": str(exc),
            }
        )
        logger.error(f"WhatsApp send failed: {exc}")
        return {"success": False, "error": str(exc), "chat_id": chat_id}


def load_history(limit: int = 50) -> List[Dict[str, Any]]:
    if not LOG_FILE.exists():
        return []
    records: List[Dict[str, Any]] = []
    with LOG_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    return records[-limit:]


def list_reports(limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
    records = load_history(limit=10000)
    records = [r for r in records if r.get("channel") == "whatsapp"]
    if status:
        records = [r for r in records if r.get("status") == status]
    return records[-limit:]


def list_internal_anomalies(limit: int = 20) -> List[Dict[str, Any]]:
    sql = """
        SELECT unique_id, tanggal_surat, nomor_nd, dari, hal, no_agenda_dispo, posisi, pic_name, status_pengiriman
        FROM surat_masuk_puu_internal
        WHERE no_agenda_dispo IS NULL OR TRIM(no_agenda_dispo) = ''
        ORDER BY tanggal_surat DESC NULLS LAST, id DESC
        LIMIT %s
    """
    rows = execute_query(sql, [limit])
    results: List[Dict[str, Any]] = []
    for row in rows:
        safe_row = {}
        for key, value in row.items():
            if isinstance(value, (datetime, date)):
                safe_row[key] = value.isoformat()
            else:
                safe_row[key] = value
        nomor_nd = row.get("nomor_nd") or "-"
        hasil = {
            "source_type": "internal_anomaly",
            "report_id": row.get("unique_id") or str(uuid.uuid4()),
            "recipient_name": os.getenv("ANOMALY_REPORT_RECIPIENT_NAME", "Pak Ahmad Haidir"),
            "recipient_phone": os.getenv("ANOMALY_REPORT_RECIPIENT_PHONE", WAHA_RECIPIENT),
            "finding_title": f"No. Agenda Dispo kosong pada surat {nomor_nd}",
            "finding_summary": "Satu record internal tidak membawa No. Agenda Dispo, sehingga perlu difilter sebagai anomali.",
            "record_key": nomor_nd,
            "source_label": row.get("dari") or "",
            "source_ref": f"unique_id={row.get('unique_id')} / nomor_nd={nomor_nd}",
            "impact": "Record tidak lolos validasi surat masuk PUU",
            "recommendation": "Koreksi data sumber atau bersihkan duplikat",
            "row": safe_row,
        }
        results.append(hasil)
    return results


def create_draft_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    report = build_report(**_report_fields(payload))
    message = report.to_message()
    record = {
        "timestamp": report.created_at,
        "report_id": report.report_id,
        "channel": "whatsapp",
        "recipient_name": report.recipient_name,
        "recipient_phone": report.recipient_phone,
        "message": message,
        "status": "draft",
        "report": asdict(report),
    }
    append_history(record)
    return record


async def send_report_by_id(report_id: str) -> Dict[str, Any]:
    records = load_history(limit=10000)
    target = None
    for rec in reversed(records):
        if rec.get("report_id") == report_id and rec.get("status") == "draft":
            target = rec
            break
    if not target:
        return {"success": False, "error": "draft_not_found"}

    report_data = target.get("report") or {}
    report = build_report(**report_data)
    message = report.to_message()
    result = await send_to_whatsapp(
        message,
        recipient_phone=report.recipient_phone,
        metadata={"report": asdict(report), "report_id": report_id},
    )
    append_history(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "report_id": report_id,
            "channel": "whatsapp",
            "recipient_name": report.recipient_name,
            "recipient_phone": report.recipient_phone,
            "message": message,
            "status": "sent" if result.get("success") else "failed",
            "result": result,
            "report": asdict(report),
        }
    )
    return {
        "success": result.get("success", False),
        "report": asdict(report),
        "message": message,
        "result": result,
    }


async def create_and_send_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    draft = create_draft_report(_report_fields(payload))
    return await send_report_by_id(draft["report_id"])
