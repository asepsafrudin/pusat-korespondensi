import os
import sys
import argparse
from pathlib import Path
from serena.agent import SerenaAgent
from serena.config.serena_config import SerenaConfig
from serena.tools import GetSymbolsOverviewTool

def trigger_indexing(project_path: str, limit=None):
    print(f"\n🚀 Indexing Project: {project_path}")
    if not os.path.exists(project_path):
        print(f"❌ Error: Path {project_path} not found.")
        return

    config = SerenaConfig.from_config_file()
    config.web_dashboard = False
    
    try:
        agent = SerenaAgent(project=project_path, serena_config=config)
        tool = agent.get_tool(GetSymbolsOverviewTool)
        
        # Discover all python files
        python_files = list(Path(project_path).rglob("*.py"))
        # Exclude common ignores
        python_files = [f for f in python_files if "venv" not in str(f) and "__pycache__" not in str(f)]
        
        print(f"📊 Found {len(python_files)} python files to scan.")
        
        if limit and isinstance(limit, int):
            python_files = python_files[:limit]
            print(f"⚠️ Limit applied: only scanning first {limit} files.")

        count = 0
        skipped = 0
        for py_file in python_files:
            rel_path = str(py_file.relative_to(project_path))
            try:
                # Use lambda to run tool in agent context
                agent.execute_task(lambda p=rel_path: tool.apply(p))
                print(f"  ✅ {rel_path}")
                count += 1
            except Exception as e:
                print(f"  ⚠️  Skipped {rel_path} (likely ignored by config)")
                skipped += 1
        
        print(f"✨ Completed: {count} indexed, {skipped} skipped.")
    except Exception as e:
        print(f"❌ Failed to start agent for {project_path}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger Serena Indexing for projects")
    parser.add_argument("--project", help="Specific project path to index")
    parser.add_argument("--limit", type=int, help="Limit number of files per project")
    args = parser.parse_args()

    if args.project:
        trigger_indexing(args.project, limit=args.limit)
    else:
        # Default projects to index based on user's earlier requests
        projects = [
            "/home/aseps/MCP/korespondensi-server",
            "/home/aseps/MCP/mcp-unified",
            "/home/aseps/MCP/infrastructure",
            "/home/aseps/MCP/xlsx-gdrive-workflow",
            "/home/aseps/MCP/services/dashboard"
        ]
        for p in projects:
            trigger_indexing(p, limit=args.limit)
