from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from .database import execute_query
from .logging_config import setup_logging

logger = setup_logging("web_app")
from .services.personnel import search_staff_pppk, get_hukum_pics
from .services.sync_service import (
    sync_internal_from_pool, 
    trigger_etl_korespondensi, 
    get_stats, 
    upload_to_gdrive,
    get_personnel_stats,
    get_letter_timeline
)
from .services.posisi_bridge import get_unique_posisi_mappings, get_unique_posisi_by_sheet, get_unique_posisi_terms
from .services.anomaly_report_service import create_draft_report, create_and_send_report, list_reports, load_history, list_internal_anomalies, send_report_by_id
from .services.mailmerge import generate_disposisi_docx

app = FastAPI(title="PUU Universal Web Hub")

# Setup templates and static files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    stats = get_stats()
    personnel_stats = get_personnel_stats()
    recent = execute_query("SELECT * FROM surat_masuk_puu_internal ORDER BY tanggal_surat DESC LIMIT 10")
    pics = get_hukum_pics()
    anomaly_reports = list_internal_anomalies(limit=10)
    anomaly_sent = list_reports(limit=5, status="sent")
    anomaly_total = len(load_history(limit=10000))
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "Dashboard PUU",
        "active_page": "dashboard",
        "stats": stats,
        "recent": recent,
        "personnel_stats": personnel_stats,
        "pics": pics[:5],
        "anomaly_reports": anomaly_reports,
        "anomaly_sent": anomaly_sent,
        "anomaly_total": anomaly_total
    })

@app.get("/internal", response_class=HTMLResponse)
async def internal_page(request: Request, q: str = "", valid_only: bool = False):
    sql = "SELECT * FROM surat_masuk_puu_internal WHERE 1=1"
    params = []
    if valid_only:
        sql += " AND no_agenda_dispo IS NOT NULL AND TRIM(no_agenda_dispo) <> ''"
    if q:
        robust_q = q.replace(".", "%").replace(" ", "%")
        sql += " AND (nomor_nd ILIKE %s OR hal ILIKE %s OR pic_name ILIKE %s OR no_agenda_dispo ILIKE %s)"
        params = [f"%{robust_q}%", f"%{robust_q}%", f"%{robust_q}%", f"%{robust_q}%"]
    sql += " ORDER BY tanggal_surat DESC LIMIT 100"
    
    rows = execute_query(sql, params)
    anomaly_count = sum(
        1 for row in rows
        if not row.get("no_agenda_dispo") or not str(row.get("no_agenda_dispo")).strip()
    )
    return templates.TemplateResponse("internal.html", {
        "request": request,
        "title": "Masuk Internal PUU",
        "active_page": "internal",
        "rows": rows,
        "query": q,
        "valid_only": valid_only,
        "anomaly_count": anomaly_count
    })

@app.get("/sync", response_class=HTMLResponse)
async def sync_page(request: Request):
    history = execute_query("SELECT * FROM correspondence_sync_runs ORDER BY started_at DESC LIMIT 10")
    stats = get_stats()
    return templates.TemplateResponse("sync.html", {
        "request": request,
        "title": "Sync Center",
        "active_page": "sync",
        "history": history,
        "stats": stats
    })

# --- API Endpoints ---

@app.get("/api/personnel/search")
async def api_search_staff(q: str):
    return search_staff_pppk(q)

@app.post("/api/internal/{unique_id}/pic")
async def api_assign_pic(unique_id: str, request: Request):
    data = await request.json()
    nama = data.get("nama")
    execute_query("UPDATE surat_masuk_puu_internal SET pic_name = %s WHERE unique_id = %s", [nama, unique_id], fetch=False)
    return {"status": "success", "pic": nama}

@app.post("/api/sync/internal")
async def api_sync_internal():
    count = sync_internal_from_pool()
    return {"count": count}

@app.get("/api/internal/{unique_id}/timeline")
async def api_get_timeline(unique_id: str):
    events = get_letter_timeline(unique_id)
    return events

@app.get("/api/knowledge/posisi/unique")
async def api_unique_posisi(limit: int = 200, q: str = ""):
    """
    Read-only bridge for distinct POSISI values and their parsed timeline.
    This is intended for sandboxed agents and IDEs that cannot reach PostgreSQL directly.
    """
    safe_limit = max(1, min(limit, 1000))
    data = get_unique_posisi_mappings(limit=safe_limit, q=q)
    return {
        "status": "success",
        "count": len(data),
        "limit": safe_limit,
        "query": q,
        "data": data,
    }

@app.get("/api/knowledge/posisi/by-sheet")
async def api_unique_posisi_by_sheet(limit_per_sheet: int = 100, q: str = ""):
    """
    Read-only bridge for distinct POSISI values grouped by source sheet.
    """
    safe_limit = max(1, min(limit_per_sheet, 1000))
    data = get_unique_posisi_by_sheet(limit_per_sheet=safe_limit, q=q)
    return {
        "status": "success",
        "count": len(data),
        "limit_per_sheet": safe_limit,
        "query": q,
        "data": data,
    }

@app.get("/api/knowledge/posisi/terms")
async def api_unique_posisi_terms(limit: int = 500, q: str = ""):
    """
    Read-only bridge for unique POSISI tokens that can be turned into a dictionary.
    """
    safe_limit = max(1, min(limit, 2000))
    data = get_unique_posisi_terms(limit=safe_limit, q=q)
    return {
        "status": "success",
        "count": len(data),
        "limit": safe_limit,
        "query": q,
        "data": data,
    }

@app.post("/api/sync/etl")
async def api_trigger_etl(bt: BackgroundTasks):
    success = trigger_etl_korespondensi()
    return {"success": success}

# --- New Phase 2 API Endpoints ---

@app.get("/api/dashboard/summary")
async def api_dashboard_summary():
    """Get summarized data for the dashboard."""
    stats = get_stats()
    personnel_stats = get_personnel_stats()
    recent = execute_query("SELECT * FROM surat_masuk_puu_internal ORDER BY tanggal_surat DESC LIMIT 10")
    pics = get_hukum_pics()
    return {
        "status": "success",
        "stats": stats,
        "recent_letters": recent,
        "personnel_stats": personnel_stats,
        "pics": pics[:5]
    }

@app.get("/api/internal/search")
async def api_internal_search(q: str = ""):
    """Search internal mail and return JSON."""
    sql = "SELECT * FROM surat_masuk_puu_internal WHERE 1=1"
    params = []
    if q:
        robust_q = q.replace(".", "%").replace(" ", "%")
        sql += " AND (nomor_nd ILIKE %s OR hal ILIKE %s OR pic_name ILIKE %s OR no_agenda_dispo ILIKE %s)"
        params = [f"%{robust_q}%", f"%{robust_q}%", f"%{robust_q}%", f"%{robust_q}%"]
    sql += " ORDER BY tanggal_surat DESC LIMIT 100"
    
    rows = execute_query(sql, params)
    return {
        "status": "success",
        "count": len(rows),
        "data": rows,
        "query": q
    }

@app.get("/api/sync/logs")
async def api_get_sync_logs(limit: int = 10):
    """Get recent sync run logs."""
    history = execute_query("SELECT * FROM correspondence_sync_runs ORDER BY started_at DESC LIMIT %s", [limit])
    return {
        "status": "success",
        "history": history
    }

@app.get("/api/anomaly-reports")
async def api_get_anomaly_reports(limit: int = 50):
    safe_limit = max(1, min(limit, 500))
    data = load_history(limit=safe_limit)
    return {
        "status": "success",
        "count": len(data),
        "data": data
    }

@app.post("/api/anomaly-reports/draft")
async def api_create_anomaly_draft(request: Request):
    payload = await request.json()
    record = create_draft_report(payload)
    return {"status": "success", "data": record}

@app.post("/api/anomaly-reports/{report_id}/send")
async def api_send_anomaly_draft(report_id: str):
    result = await send_report_by_id(report_id)
    return {
        "status": "success" if result.get("success") else "error",
        "data": result
    }

@app.post("/api/anomaly-reports/send")
async def api_send_anomaly_report(request: Request):
    payload = await request.json()
    result = await create_and_send_report(payload)
    return {
        "status": "success" if result.get("success") else "error",
        "data": result
    }

@app.post("/api/disposisi/generate/{unique_id}")
async def api_generate_and_link(unique_id: str):
    """Generate DOCX, upload to GDrive synchronously, and return the link."""
    try:
        # 1. Generate local file
        from .services.mailmerge import generate_disposisi_docx
        from .services.sync_service import upload_to_gdrive
        
        file_path = generate_disposisi_docx(unique_id)
        
        # 2. Upload synchronously (we need the link now)
        # Modified upload_to_gdrive should return the link
        drive_url = upload_to_gdrive(file_path, unique_id)
        
        if not drive_url:
            # Fallback if upload fails but file exists
            return {"status": "partial", "message": "File generated but failed to upload.", "local_path": file_path}
            
        return {
            "status": "success", 
            "drive_url": drive_url,
            "filename": os.path.basename(file_path)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/disposisi/download/{unique_id}")
async def download_disposisi(unique_id: str, background_tasks: BackgroundTasks):
    """Legacy download endpoint (still works for direct links)."""
    try:
        res = execute_query("SELECT drive_file_url FROM surat_masuk_puu_internal WHERE unique_id = %s", [unique_id])
        if res and res[0].get('drive_file_url'):
            return RedirectResponse(url=res[0]['drive_file_url'])
            
        from .services.mailmerge import generate_disposisi_docx
        file_path = generate_disposisi_docx(unique_id)
        background_tasks.add_task(upload_to_gdrive, file_path, unique_id)
        return FileResponse(path=file_path, filename=os.path.basename(file_path))
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/struktur", response_class=HTMLResponse)
async def struktur_page(request: Request):
    """Organizational structure diagram page."""
    import json
    json_path = os.path.join(os.path.dirname(__file__), "master_struktur_bangda_2025.json")
    with open(json_path, "r", encoding="utf-8") as f:
        struktur_data = json.load(f)
    return templates.TemplateResponse("struktur.html", {
        "request": request,
        "title": "Struktur Organisasi",
        "active_page": "struktur",
        "struktur_data": struktur_data
    })

# --- Shared Layout Dummy Route for development ---
@app.exception_handler(404)
async def custom_404_handler(request: Request, __):
    return templates.TemplateResponse("base.html", {"request": request, "active_page": "dashboard"})
