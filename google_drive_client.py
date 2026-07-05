"""
Google Drive Client for uploading model files
Handles OAuth authentication and file uploads to Google Drive
"""

import os
import pickle
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

# Scopes for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GoogleDriveClient:
    def __init__(self, credentials_file='google_credentials.json'):
        """Initialize Google Drive client with OAuth credentials"""
        self.credentials_file = credentials_file
        self.token_file = Path(credentials_file).parent / 'google_token.pickle'
        self.service = None
        self.creds = None

    def authenticate(self):
        """Authenticate with Google Drive using OAuth"""
        try:
            # Load existing token if available
            if self.token_file.exists():
                with open(self.token_file, 'rb') as f:
                    self.creds = pickle.load(f)

            # Refresh if expired or create new auth flow
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    if not Path(self.credentials_file).exists():
                        raise FileNotFoundError(
                            f"Google credentials file not found: {self.credentials_file}\n\n"
                            "Please download OAuth credentials from Google Cloud Console and save as google_credentials.json"
                        )

                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, SCOPES)
                    self.creds = flow.run_local_server(port=0)

                # Save token for next time
                with open(self.token_file, 'wb') as f:
                    pickle.dump(self.creds, f)

            # Build the Drive service
            self.service = discovery.build('drive', 'v3', credentials=self.creds)
            return True

        except Exception as e:
            print(f"Authentication error: {e}")
            raise

    def upload_file(self, file_path, folder_id=None, file_name=None, progress_callback=None):
        """
        Upload file to Google Drive

        Args:
            file_path: Path to file to upload
            folder_id: Google Drive folder ID (None = root)
            file_name: Name for file on Drive (default: original name)
            progress_callback: Function to call with progress (0-100)

        Returns:
            dict with 'id' and 'webViewLink' (shareable link)
        """
        try:
            if not self.service:
                self.authenticate()

            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            file_name = file_name or file_path.name
            file_size = file_path.stat().st_size

            # File metadata
            file_metadata = {
                'name': file_name,
                'mimeType': 'application/zip'
            }

            if folder_id:
                file_metadata['parents'] = [folder_id]

            # Upload file
            print(f"Uploading {file_name} ({file_size / (1024*1024):.2f} MB)...")
            if progress_callback:
                progress_callback(0, "Starting upload...")

            media = discovery.MediaFileUpload(
                str(file_path),
                mimetype='application/zip',
                resumable=True,
                chunksize=10 * 1024 * 1024  # 10MB chunks
            )

            # Upload with progress tracking
            request = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink, webContentLink'
            )

            file = None
            while file is None:
                status, file = request.next_chunk()
                if status:
                    progress_pct = int(status.progress() * 100)
                    print(f"Upload progress: {progress_pct}%")
                    if progress_callback:
                        progress_callback(progress_pct, f"Uploading... {progress_pct}%")

            print(f"Upload complete! File ID: {file.get('id')}")

            # Make file publicly accessible (shareable)
            self.service.permissions().create(
                fileId=file.get('id'),
                body={
                    'kind': 'drive#permission',
                    'type': 'anyone',
                    'role': 'reader'
                }
            ).execute()

            return {
                'id': file.get('id'),
                'name': file_name,
                'webViewLink': file.get('webViewLink'),
                'webContentLink': file.get('webContentLink'),
                'downloadLink': f"https://drive.google.com/uc?id={file.get('id')}&export=download"
            }

        except Exception as e:
            print(f"Upload error: {e}")
            raise

    def create_folder(self, folder_name, parent_id=None):
        """
        Create folder in Google Drive

        Args:
            folder_name: Name of folder
            parent_id: Parent folder ID (None = root)

        Returns:
            Folder ID
        """
        try:
            if not self.service:
                self.authenticate()

            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }

            if parent_id:
                folder_metadata['parents'] = [parent_id]

            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()

            return folder.get('id')

        except Exception as e:
            print(f"Folder creation error: {e}")
            raise

    def get_shareable_link(self, file_id):
        """Get shareable link for a file"""
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='webViewLink, webContentLink'
            ).execute()

            return {
                'viewLink': file.get('webViewLink'),
                'downloadLink': f"https://drive.google.com/uc?id={file_id}&export=download"
            }

        except Exception as e:
            print(f"Link retrieval error: {e}")
            raise

    def list_files(self, query=None, max_results=20):
        """
        List files from Google Drive

        Args:
            query: Search query (e.g., "name contains '.zip'")
            max_results: Maximum number of results to return

        Returns:
            List of files with id, name, webViewLink, webContentLink
        """
        try:
            if not self.service:
                self.authenticate()

            query = query or "trashed=false"

            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, mimeType, createdTime, modifiedTime, webViewLink, webContentLink)',
                pageSize=max_results,
                orderBy='modifiedTime desc'
            ).execute()

            files = results.get('files', [])
            print(f"Found {len(files)} files matching query: {query}")
            return files

        except Exception as e:
            print(f"List files error: {e}")
            raise
