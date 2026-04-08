import os
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

# Database connection parameters
DB_CONFIG = {
    "host": os.getenv("PG_HOST", "localhost"),
    "port": int(os.getenv("PG_PORT", "5433")),
    "dbname": os.getenv("PG_DATABASE", "mcp_knowledge"),
    "user": os.getenv("PG_USER", "mcp_user"),
    "password": os.getenv("PG_PASSWORD", "mcp_password_2024"),
    "row_factory": dict_row
}

# Initialize global connection pool
# We use min_size=1, max_size=10 to handle concurrent requests from Web and MCP
pool = ConnectionPool(
    psycopg.utils.conninfo_to_string(**DB_CONFIG),
    min_size=1,
    max_size=10,
    open=True
)

def get_db_connection():
    """Get a connection from the pool."""
    return pool.connection()

def execute_query(query, params=None, fetch=True):
    """Utility to execute a query using the connection pool."""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or [])
            if fetch:
                return cur.fetchall()
            conn.commit()
            return None
