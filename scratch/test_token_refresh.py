
import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

TOKEN_FILE = "/home/aseps/MCP/config/credentials/google/puubangda/token.json"

def test_refresh():
    if not os.path.exists(TOKEN_FILE):
        print("Token file not found.")
        return
        
    with open(TOKEN_FILE, 'r') as f:
        data = json.load(f)
        creds = Credentials.from_authorized_user_file(TOKEN_FILE)
        
    print(f"Current token expired: {creds.expired}")
    
    if creds.refresh_token:
        try:
            print("Refreshing token...")
            creds.refresh(Request())
            print("Refresh success!")
            with open(TOKEN_FILE, 'w') as f:
                f.write(creds.to_json())
        except Exception as e:
            print(f"Refresh failed: {e}")
    else:
        print("No refresh token found.")

if __name__ == "__main__":
    test_refresh()
