import os
import sys
import argparse
import uvicorn
import asyncio
import logging

# Add current directory to path for relative imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.web_app import app as web_app
from src.mcp_server import KorespondensiMCP

from src.logging_config import setup_logging

logger = setup_logging("main")

def run_web():
    """Run the FastAPI Web Application."""
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "8082"))
    print(f"🚀 Starting PUU Universal Web Hub on http://{host}:{port}")
    uvicorn.run(web_app, host=host, port=port)

def run_mcp():
    """Run the MCP Server (stdio)."""
    mcp = KorespondensiMCP()
    asyncio.run(mcp.run())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PUU Universal Server & Web Hub")
    parser.add_argument("--mode", choices=["web", "mcp"], default="web", help="Mode to run (default: web)")
    
    args = parser.parse_args()
    
    if args.mode == "web":
        run_web()
    elif args.mode == "mcp":
        run_mcp()
