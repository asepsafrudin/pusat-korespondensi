import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

def migrate():
    dsn = f"host={os.getenv('PG_HOST')} port={os.getenv('PG_PORT')} dbname={os.getenv('PG_DATABASE')} user={os.getenv('PG_USER')} password={os.getenv('PG_PASSWORD')}"
    
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                print("Checking table surat_keluar_puu...")
                # Add status_pengiriman and posisi to surat_keluar_puu if not exists
                cur.execute("""
                    DO $$ 
                    BEGIN 
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                     WHERE table_name='surat_keluar_puu' AND column_name='status_pengiriman') THEN
                            ALTER TABLE surat_keluar_puu ADD COLUMN status_pengiriman VARCHAR(100);
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                     WHERE table_name='surat_keluar_puu' AND column_name='posisi') THEN
                            ALTER TABLE surat_keluar_puu ADD COLUMN posisi TEXT;
                        END IF;
                    END $$;
                """)
                
                # Backfill existing surat_keluar_puu with 'Arsip Final'
                cur.execute("UPDATE surat_keluar_puu SET status_pengiriman = 'Arsip Final' WHERE status_pengiriman IS NULL")
                
                print("Ensuring vault_events table exists...")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vault_events (
                        id SERIAL PRIMARY KEY,
                        letter_id BIGINT NOT NULL REFERENCES surat_keluar_puu(id) ON DELETE CASCADE,
                        event_type TEXT NOT NULL,
                        event_value TEXT NOT NULL,
                        event_at TIMESTAMP WITH TIME ZONE,
                        event_meta JSONB NOT NULL DEFAULT '{}',
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_vault_events_letter_id ON vault_events(letter_id);
                """)
                
                print("Checking table surat_masuk_puu_internal...")
                # Ensure surat_masuk_puu_internal has the column (it should, but just in case)
                cur.execute("""
                    DO $$ 
                    BEGIN 
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                     WHERE table_name='surat_masuk_puu_internal' AND column_name='status_pengiriman') THEN
                            ALTER TABLE surat_masuk_puu_internal ADD COLUMN status_pengiriman VARCHAR(100);
                        END IF;
                    END $$;
                """)
                
                print("Migration successful.")
            conn.commit()
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
