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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)

def run_web():
    """Run the FastAPI Web Application."""
    print("🚀 Starting PUU Universal Web Hub on http://0.0.0.0:8081")
    uvicorn.run(web_app, host="0.0.0.0", port=8081)

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
