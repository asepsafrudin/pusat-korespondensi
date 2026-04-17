import os
import sys
import json

# Add mcp-unified to path
sys.path.append('/home/aseps/MCP/mcp-unified')

# Set environment variables for secrets loading
os.environ["GOOGLE_WORKSPACE_CREDENTIALS_PATH"] = "/home/aseps/MCP/config/credentials/google/puubangda"
os.environ["GOOGLE_WORKSPACE_TOKEN_FILE"] = "token.json"

from integrations.google_workspace.client import get_google_client
from googleapiclient.discovery import build

folder_id = '1RQJki7P0aMLra3cCR5QnyQmTMW5xn47m'

def list_with_shared_drives():
    client = get_google_client()
    if not client.connect():
        print("Failed to connect via Unified Client")
        return
    
    drive = build('drive', 'v3', credentials=client._credentials)
    
    print(f"Listing folder {folder_id} (including shared drives)...")
    try:
        # Check folder info first
        folder_info = drive.files().get(fileId=folder_id, fields="id, name, mimeType", supportsAllDrives=True).execute()
        print(f"Folder found: {folder_info['name']} ({folder_info['mimeType']})")
        
        query = f"'{folder_id}' in parents and trashed = false"
        results = drive.files().list(
            q=query,
            pageSize=100,
            fields="files(id, name, mimeType, size)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        files = results.get('files', [])
        print(json.dumps(files, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_with_shared_drives()
