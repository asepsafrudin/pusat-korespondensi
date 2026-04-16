from __future__ import annotations

import json
import os
import uuid
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional

# Bootstrap mcp-unified path
MCP_UNIFIED_ROOT = Path(os.getenv("MCP_UNIFIED_ROOT", "/home/aseps/MCP/mcp-unified"))
if str(MCP_UNIFIED_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_UNIFIED_ROOT))

from core.reporting.service import UniversalReport, get_reporting_service
from ..database import execute_query
from ..logging_config import setup_logging

logger = setup_logging("anomaly_report_service")

# Note: We keep the local logging directory for backward compatibility with existing dashboard views
LOG_DIR = Path(os.getenv("KORESPONDESI_LOG_DIR", "/home/aseps/MCP/korespondensi-server/logs"))
LOG_FILE = Path(os.getenv("ANOMALY_REPORT_LOG_FILE", str(LOG_DIR / "anomaly_reports.jsonl")))
WAHA_RECIPIENT = os.getenv("WHATSAPP_RECIPIENT", "6287871393744")

@dataclass
class AnomalyReport:
    """Legacy compatibility dataclass for Korespondensi Anomalies."""
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
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_universal(self) -> UniversalReport:
        """Map legacy report to the new Universal format."""
        return UniversalReport(
            recipient_name=self.recipient_name,
            recipient_phone=self.recipient_phone,
            title=self.finding_title,
            summary=self.finding_summary,
            details={
                "kunci_data": self.record_key,
                "sumber": self.source_label,
                "referensi": self.source_ref
            },
            impact=self.impact,
            recommendation=self.recommendation,
            report_type="anomaly",
            reporter_name=self.reporter_name,
            report_id=self.report_id,
            created_at=self.created_at
        )

def _append_local_history(record: Dict[str, Any]):
    """Keep local JSONL updated so the dashboard UI doesn't break."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

def list_internal_anomalies(limit: int = 20) -> List[Dict[str, Any]]:
    """Business logic for detecting anomalies in korespondensi database."""
    sql = """
        SELECT unique_id, tanggal_surat, nomor_nd, dari, hal, no_agenda_dispo, posisi, pic_name, status_pengiriman
        FROM surat_masuk_puu_internal
        WHERE no_agenda_dispo IS NULL OR TRIM(no_agenda_dispo) = ''
        ORDER BY tanggal_surat DESC NULLS LAST, id DESC
        LIMIT %s
    """
    rows = execute_query(sql, [limit])
    results = []
    for row in rows:
        safe_row = {k: (v.isoformat() if isinstance(v, (datetime, date)) else v) for k, v in row.items()}
        nomor_nd = row.get("nomor_nd") or "-"
        
        reasons = []
        if row.get("no_agenda_dispo") is None or str(row.get("no_agenda_dispo")).strip() == "":
            reasons.append("Kolom no_agenda_dispo kosong")
        
        if nomor_nd and nomor_nd != "-":
            dupe = execute_query("SELECT COUNT(*) as cnt FROM surat_masuk_puu_internal WHERE nomor_nd = %s", [nomor_nd])
            if dupe and dupe[0]["cnt"] > 1:
                reasons.append(f"Duplikat nomor_nd (total: {dupe[0]['cnt']})")
        
        reason_explanation = "; ".join(reasons)
        hasil = {
            "source_type": "internal_anomaly",
            "report_id": row.get("unique_id") or str(uuid.uuid4()),
            "recipient_name": os.getenv("ANOMALY_REPORT_RECIPIENT_NAME", "Pak Ahmad Haidir"),
            "recipient_phone": WAHA_RECIPIENT,
            "finding_title": f"No. Agenda Dispo kosong pada surat {nomor_nd}",
            "finding_summary": f"Satu record internal tidak membawa No. Agenda Dispo. Alasan: {reason_explanation}",
            "reason_explanation": reason_explanation,
            "record_key": nomor_nd,
            "source_label": row.get("dari") or "",
            "source_ref": f"unique_id={row.get('unique_id')}",
            "impact": "Record tidak lolos validasi surat masuk PUU",
            "recommendation": "Koreksi data sumber atau bersihkan duplikat",
            "row": safe_row,
        }
        results.append(hasil)
    return results

def create_draft_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a draft using the universal service mapping."""
    # Filter payload
    allowed = {"recipient_name", "recipient_phone", "finding_title", "finding_summary", "record_key", "source_label", "source_ref", "impact", "recommendation"}
    filtered_payload = {k: v for k, v in payload.items() if k in allowed}
    
    report = AnomalyReport(**filtered_payload)
    record = {
        "timestamp": report.created_at,
        "report_id": report.report_id,
        "channel": "whatsapp",
        "recipient_name": report.recipient_name,
        "recipient_phone": report.recipient_phone,
        "message": report.to_universal().to_whatsapp_message(),
        "status": "draft",
        "report": asdict(report),
    }
    _append_local_history(record)
    return record

async def send_report_by_id(report_id: str) -> Dict[str, Any]:
    """Send report via Universal Reporting Service."""
    # Find draft in local history
    records = []
    if LOG_FILE.exists():
        with LOG_FILE.open("r") as f:
            for line in f:
                try: records.append(json.loads(line))
                except: continue
    
    target = next((r for r in reversed(records) if r.get("report_id") == report_id and r.get("status") == "draft"), None)
    if not target:
        return {"success": False, "error": "draft_not_found"}

    report_data = target.get("report") or {}
    legacy_report = AnomalyReport(**report_data)
    universal_report = legacy_report.to_universal()
    
    service = get_reporting_service()
    result = await service.send_report(universal_report, channel="whatsapp")
    
    # Update local history
    _append_local_history({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "report_id": report_id,
        "channel": "whatsapp",
        "status": "sent" if result.get("success") else "failed",
        "result": result,
        "report": report_data,
    })
    
    return result

async def create_and_send_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    draft = create_draft_report(payload)
    return await send_report_by_id(draft["report_id"])

def load_history(limit: int = 50) -> List[Dict[str, Any]]:
    if not LOG_FILE.exists(): return []
    records = []
    with LOG_FILE.open("r") as f:
        for line in f:
            try: records.append(json.loads(line))
            except: continue
    return records[-limit:]

def list_reports(limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
    records = [r for r in load_history(limit=1000) if r.get("status") == status or status is None]
    return records[-limit:]
