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
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "Dashboard PUU",
        "active_page": "dashboard",
        "stats": stats,
        "recent": recent,
        "personnel_stats": personnel_stats,
        "pics": pics[:5]
    })

@app.get("/internal", response_class=HTMLResponse)
async def internal_page(request: Request, q: str = ""):
    sql = "SELECT * FROM surat_masuk_puu_internal WHERE 1=1"
    params = []
    if q:
        robust_q = q.replace(".", "%").replace(" ", "%")
        sql += " AND (nomor_nd ILIKE %s OR hal ILIKE %s OR pic_name ILIKE %s OR no_agenda_dispo ILIKE %s)"
        params = [f"%{robust_q}%", f"%{robust_q}%", f"%{robust_q}%", f"%{robust_q}%"]
    sql += " ORDER BY tanggal_surat DESC LIMIT 100"
    
    rows = execute_query(sql, params)
    return templates.TemplateResponse("internal.html", {
        "request": request,
        "title": "Masuk Internal PUU",
        "active_page": "internal",
        "rows": rows,
        "query": q
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

@app.get("/api/disposisi/download/{unique_id}")
async def download_disposisi(unique_id: str, background_tasks: BackgroundTasks):
    try:
        # Cek ketersediaan di database terlebih dahulu (Single Source of Truth)
        res = execute_query("SELECT drive_file_url FROM surat_masuk_puu_internal WHERE unique_id = %s", [unique_id])
        if res and res[0].get('drive_file_url'):
            return RedirectResponse(url=res[0]['drive_file_url'])
            
        file_path = generate_disposisi_docx(unique_id)
        # Tambahkan tugas belakang layar agar unggahan ke Google Drive tak hambat klien
        background_tasks.add_task(upload_to_gdrive, file_path, unique_id)
        return FileResponse(
            path=file_path, 
            filename=os.path.basename(file_path),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

# --- Shared Layout Dummy Route for development ---
@app.exception_handler(404)
async def custom_404_handler(request: Request, __):
    return templates.TemplateResponse("base.html", {"request": request, "active_page": "dashboard"})
