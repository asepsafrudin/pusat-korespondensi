import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Token path
token_path = '/home/aseps/MCP/config/credentials/google/puubangda/token.json'
folder_id = '1RQJki7P0aMLra3cCR5QnyQmTMW5xn47m'

def list_folder_user():
    if not os.path.exists(token_path):
        print(f"Token file not found: {token_path}")
        return

    with open(token_path, 'r') as f:
        token_data = json.load(f)
    
    # Define scopes needed
    scopes = [
        "https://www.googleapis.com/auth/drive.metadata.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file"
    ]
    
    creds = Credentials.from_authorized_user_file(token_path, scopes)
    
    try:
        service = build('drive', 'v3', credentials=creds)
        
        print(f"Listing files in folder: {folder_id}...")
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType)"
        ).execute()
        
        items = results.get('files', [])
        if not items:
            print('No files found.')
        else:
            print(json.dumps(items, indent=2))
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    list_folder_user()
