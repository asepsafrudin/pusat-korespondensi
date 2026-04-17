import sys
import os
import json

# Add mcp-unified to path
sys.path.append('/home/aseps/MCP/mcp-unified')

from integrations.gdrive.client import GDriveClient

# Folder ID from user
folder_id = '1RQJki7P0aMLra3cCR5QnyQmTMW5xn47m'

# Service account path (found in find command)
creds_path = '/home/aseps/MCP/config/credentials/google/mcp-gmail-482015-682b788ee191.json'

def list_folder():
    client = GDriveClient(credentials_path=creds_path)
    if not client.connect():
        print("Failed to connect to Google Drive")
        return

    print(f"Listing files in folder: {folder_id}...")
    files = client.list_files(folder_id=folder_id)
    
    result = []
    for f in files:
        result.append({
            "id": f.id,
            "name": f.name,
            "mime_type": f.mime_type,
            "size": f.size
        })
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    list_folder()
