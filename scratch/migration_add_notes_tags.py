import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

def add_notes_and_tags():
    dsn = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DATABASE')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                print("Adding notes and tags to correspondence tables...")
                
                # Table: surat_masuk_puu_internal
                cur.execute("""
                    ALTER TABLE surat_masuk_puu_internal 
                    ADD COLUMN IF NOT EXISTS catatan TEXT,
                    ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb;
                """)
                
                # Table: surat_keluar_puu
                cur.execute("""
                    ALTER TABLE surat_keluar_puu 
                    ADD COLUMN IF NOT EXISTS catatan TEXT,
                    ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb;
                """)
                
                print("Schema updated successfully.")
            conn.commit()
    except Exception as e:
        print(f"Update failed: {e}")

if __name__ == "__main__":
    add_notes_and_tags()
