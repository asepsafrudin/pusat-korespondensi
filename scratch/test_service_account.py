
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

SERVICE_ACCOUNT_FILE = "/home/aseps/MCP/config/credentials/google/mcp-gmail-482015-682b788ee191.json"
FOLDER_ID = "1s1WyweDstV0vYgP1SIfQk4rWwDGO0OYw"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def test_service_account():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print("Service account file not found.")
        return
        
    try:
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)
        
        # Test listing files in the folder
        results = service.files().list(
            q=f"'{FOLDER_ID}' in parents",
            pageSize=5,
            fields="nextPageToken, files(id, name)"
        ).execute()
        
        items = results.get('files', [])
        print(f"Items in folder {FOLDER_ID}:")
        for item in items:
            print(f"- {item['name']} ({item['id']})")
        print("Success! Service account can access the folder.")
        
    except Exception as e:
        print(f"Service account test failed: {e}")

if __name__ == "__main__":
    test_service_account()
