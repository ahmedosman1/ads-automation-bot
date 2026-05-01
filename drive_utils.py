
import os
import io
import re
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def get_file_id_from_link(link):
    """Extracts the file ID from a Google Drive sharing link."""
    match = re.search(r'[-\w]{25,}', link)
    return match.group(0) if match else None

def download_file_from_drive(file_id, output_path):
    """Downloads a file from Google Drive using its file ID."""
    # Note: In a real scenario, you'd need to handle OAuth2 refresh tokens properly
    # For this example, we assume environment variables are set for credentials
    creds = Credentials(
        None,
        refresh_token=os.getenv("GOOGLE_DRIVE_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_DRIVE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_DRIVE_CLIENT_SECRET"),
    )
    
    if not creds.valid:
        creds.refresh(Request())

    service = build('drive', 'v3', credentials=creds)
    
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(output_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print(f"Download {int(status.progress() * 100)}%.")
    
    return output_path
