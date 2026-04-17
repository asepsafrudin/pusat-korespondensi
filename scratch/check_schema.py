
import os
import sys
from dotenv import load_dotenv

sys.path.append('/home/aseps/MCP/korespondensi-server')
from src.database import execute_query

def check_schema():
    print("Columns for surat_keluar_puu:")
    res = execute_query("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'surat_keluar_puu'
    """)
    for r in res:
        print(f" - {r['column_name']} ({r['data_type']})")

if __name__ == "__main__":
    load_dotenv('/home/aseps/MCP/korespondensi-server/.env')
    check_schema()
