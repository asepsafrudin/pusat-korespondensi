import json
import psycopg
import os
from dotenv import load_dotenv

load_dotenv()

def sync_db():
    enrichment_path = '/home/aseps/MCP/korespondensi-server/src/Qwen_json_20260416_b2j90or5b.json'
    sql_path = '/home/aseps/MCP/korespondensi-server/src/Qwen_sql_20260416_qgrowe7kf.sql'
    
    with open(enrichment_path, 'r') as f:
        enrichment_data = json.load(f)
    
    conn_str = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DATABASE')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            # 1. Clear old data
            cur.execute("TRUNCATE TABLE master_json RESTART IDENTITY CASCADE")
            cur.execute("TRUNCATE TABLE staff_details RESTART IDENTITY CASCADE")
            
            # 2. Insert the JSON wrapper into master_json
            # The SQL script expects d->'staf_operasional' from jsonb_array_elements(detail_enrichment)
            # So we insert the 'detail_enrichment' list directly
            cur.execute("INSERT INTO master_json (detail_enrichment) VALUES (%s)", (json.dumps(enrichment_data['detail_enrichment']),))
            
            # 3. Read and execute the SQL script from Qwen
            with open(sql_path, 'r') as f:
                sql_script = f.read()
            
            print(f"Executing sync SQL:\n{sql_script}")
            cur.execute(sql_script)
            
            conn.commit()
            
            # 4. Verify
            cur.execute("SELECT COUNT(*) FROM staff_details")
            count = cur.fetchone()[0]
            print(f"Sync complete. Total staff imported: {count}")

if __name__ == "__main__":
    sync_db()
