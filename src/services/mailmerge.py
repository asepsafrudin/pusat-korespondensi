import os
from datetime import datetime
from docxtpl import DocxTemplate
from fastapi.responses import FileResponse
from ..database import execute_query
from ..logging_config import setup_logging

logger = setup_logging("mailmerge")

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
    "templates_doc", 
    "template_disposisi_native.docx"
)

def format_tgl(d):
    if not d: return "-"
    from datetime import date, datetime
    if isinstance(d, str):
        try: d = date.fromisoformat(d.split("T")[0])
        except: return d
    
    bulan_indo = {
        1:"Januari", 2:"Februari", 3:"Maret", 4:"April", 5:"Mei", 6:"Juni",
        7:"Juli", 8:"Agustus", 9:"September", 10:"Oktober", 11:"November", 12:"Desember"
    }
    return f"{d.day:02d} {bulan_indo.get(d.month, '')} {d.year}"

def generate_disposisi_docx(unique_id: str) -> str:
    """Read DB, fill template, and save to /tmp."""
    rows = execute_query(
        "SELECT * FROM surat_masuk_puu_internal WHERE unique_id = %s", 
        [unique_id]
    )
    if not rows:
        raise ValueError("Data surat tidak ditemukan")
    
    data = rows[0]
    
    # Render template
    doc = DocxTemplate(TEMPLATE_PATH)
    
    agenda_dispo = data.get('no_agenda_dispo') or '-'
    
    context = {
        "direktorat": data.get('dari', '-'),
        "nomor_nd": data.get('nomor_nd', '-'),
        "tanggal_surat": format_tgl(data.get('tanggal_surat')),
        "hal": data.get('hal', '-'),
        "tgl_diterima": format_tgl(data.get('tanggal_diterima_puu')) if data.get('tanggal_diterima_puu') else "                     /               / 2026",
        "no_agenda_ses": agenda_dispo,
        "agenda_puu": data.get('agenda_puu', agenda_dispo)
    }
    
    doc.render(context)
    
    # Save to tmp
    safe_agenda = str(agenda_dispo).replace("/", "_")
    output_filename = f"/tmp/Disposisi_{safe_agenda}.docx"
    doc.save(output_filename)
    
    return output_filename
