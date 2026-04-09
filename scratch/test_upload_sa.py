
import os
import json
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SERVICE_ACCOUNT_FILE = "/home/aseps/MCP/config/credentials/google/mcp-gmail-482015-682b788ee191.json"
FOLDER_ID = "1s1WyweDstV0vYgP1SIfQk4rWwDGO0OYw"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

def test_upload():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print("Service account file not found.")
        return
        
    try:
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)
        
        # Test creating a small file
        file_metadata = {
            'name': 'test_upload_sa.txt',
            'parents': [FOLDER_ID]
        }
        media = MediaIoBaseUpload(io.BytesIO(b'Hello from SA'), mimetype='text/plain')
        
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"Upload success! File ID: {file.get('id')}")
        
    except Exception as e:
        print(f"Service account upload test failed: {e}")

if __name__ == "__main__":
    test_upload()
