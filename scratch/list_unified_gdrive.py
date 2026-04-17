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

def list_with_unified_client():
    client = get_google_client()
    if not client.connect():
        print("Failed to connect via Unified Client")
        return
    
    print(f"Authenticated as: {client._credentials.service_account_email if hasattr(client._credentials, 'service_account_email') else 'User'}")
    
    # Build Drive service using unified credentials
    drive = build('drive', 'v3', credentials=client._credentials)
    
    print(f"Listing folder {folder_id}...")
    try:
        query = f"'{folder_id}' in parents and trashed = false"
        results = drive.files().list(
            q=query,
            pageSize=100,
            fields="files(id, name, mimeType, size)"
        ).execute()
        
        files = results.get('files', [])
        print(json.dumps(files, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_with_unified_client()
