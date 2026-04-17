
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append('/home/aseps/MCP/korespondensi-server')

from src.database import execute_query

def check_statuses():
    print("Checking surat_masuk_puu_internal statuses:")
    res = execute_query("SELECT DISTINCT status_pengiriman FROM surat_masuk_puu_internal")
    for r in res:
        print(f" - {r.get('status_pengiriman')}")
        
    print("\nChecking surat_keluar_puu statuses:")
    try:
        res = execute_query("SELECT DISTINCT status_pengiriman FROM surat_keluar_puu")
        for r in res:
            print(f" - {r.get('status_pengiriman')}")
    except Exception as e:
        print(f"Error checking surat_keluar_puu: {e}")

if __name__ == "__main__":
    load_dotenv('/home/aseps/MCP/korespondensi-server/.env')
    check_statuses()
