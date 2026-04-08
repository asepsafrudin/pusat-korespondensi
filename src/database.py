import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """Establish connection to mcp_knowledge database with dict_row factory."""
    return psycopg.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5433")),
        dbname=os.getenv("PG_DATABASE", "mcp_knowledge"),
        user=os.getenv("PG_USER", "mcp_user"),
        password=os.getenv("PG_PASSWORD", "mcp_password_2024"),
        row_factory=dict_row
    )

def execute_query(query, params=None, fetch=True):
    """Utility to execute a query and return results."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or [])
            if fetch:
                return cur.fetchall()
            conn.commit()
            return None
