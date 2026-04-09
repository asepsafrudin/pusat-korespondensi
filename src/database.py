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
# We strip row_factory from DB_CONFIG as it's not a valid connection parameter string
conn_params = {k: v for k, v in DB_CONFIG.items() if k != "row_factory"}
conn_str = " ".join([f"{k}={v}" for k, v in conn_params.items()])

pool = ConnectionPool(
    conn_str,
    min_size=1,
    max_size=10,
    open=True,
    kwargs={"row_factory": dict_row}
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
                rows = cur.fetchall()
                if not rows:
                    return []
                # Manual conversion to ensure dicts regardless of driver behavior
                colnames = [desc[0] for desc in cur.description]
                results = []
                for row in rows:
                    if isinstance(row, dict):
                        results.append(row)
                    else:
                        results.append(dict(zip(colnames, row)))
                return results
            conn.commit()
            return None
