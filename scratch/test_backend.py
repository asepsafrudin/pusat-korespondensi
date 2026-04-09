
import os
from src.database import execute_query
from src.services.sync_service import get_stats

try:
    stats = get_stats()
    print(f"Stats: {stats}")
    rows = execute_query("SELECT * FROM surat_masuk_puu_internal LIMIT 1")
    print(f"Data Sample: {rows}")
except Exception as e:
    print(f"Error: {e}")
