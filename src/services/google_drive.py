import logging
import os
from typing import Dict, List, Optional, Union

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from PIL import Image

logger = logging.getLogger(__name__)


class GoogleDriveService:
    """Service for interacting with Google Drive including shared drives."""

    def __init__(self, credentials_file: str, shared_drive_id: Optional[str] = None):
        """Initialize the Google Drive service.

        Args:
            credentials_file: Path to the Google API credentials file.
            shared_drive_id: Optional ID of the shared drive to use.
        """
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=["https://www.googleapis.com/auth/drive"]
        )
        self.service = build("drive", "v3", credentials=self.credentials)
        self.shared_drive_id = shared_drive_id

    def list_files(self, folder_id: str) -> List[Dict]:
        """List all files in a folder.

        Args:
            folder_id: ID of the folder to list files from.

        Returns:
            List of file metadata dictionaries.
        """
        results = []
        page_token = None

        # Prepare query parameters
        params = {
            "q": f"'{folder_id}' in parents and trashed=false",
            "spaces": "drive",
            "fields": "nextPageToken, files(id, name, mimeType)",
            "pageToken": page_token,
        }

        # Add shared drive parameters if applicable
        if self.shared_drive_id:
            params.update(
                {
                    "corpora": "drive",
                    "driveId": self.shared_drive_id,
                    "includeItemsFromAllDrives": True,
                    "supportsAllDrives": True,
                }
            )

        while True:
            response = self.service.files().list(**params).execute()

            results.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            params["pageToken"] = page_token

            if not page_token:
                break

        return results

    def create_folder(self, parent_id: str, name: str) -> str:
        """Create a folder in Google Drive.

        Args:
            parent_id: ID of the parent folder.
            name: Name of the folder to create.

        Returns:
            ID of the created folder.
        """
        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }

        # Prepare parameters
        params = {"body": file_metadata, "fields": "id"}

        # Add shared drive support if applicable
        if self.shared_drive_id:
            params["supportsAllDrives"] = True

        folder = self.service.files().create(**params).execute()
        logger.info(f"Created folder '{name}' with ID: {folder.get('id')}")
        return folder.get("id")

    def find_folder(self, parent_id: str, folder_name: str) -> Optional[str]:
        """Find a folder by name within a parent folder.

        Args:
            parent_id: ID of the parent folder.
            folder_name: Name of the folder to find.

        Returns:
            ID of the found folder or None if not found.
        """
        query = (
            f"'{parent_id}' in parents and name = '{folder_name}' and"
            " mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )

        # Prepare parameters
        params = {"q": query, "spaces": "drive", "fields": "files(id, name)"}

        # Add shared drive support if applicable
        if self.shared_drive_id:
            params.update(
                {
                    "corpora": "drive",
                    "driveId": self.shared_drive_id,
                    "includeItemsFromAllDrives": True,
                    "supportsAllDrives": True,
                }
            )

        response = self.service.files().list(**params).execute()
        files = response.get("files", [])

        if files:
            logger.info(f"Found existing folder '{folder_name}' with ID: {files[0].get('id')}")
            return files[0].get("id")

        return None

    def find_or_create_folder(self, name: str, parent_id: str) -> str:
        """Find a folder by name or create it if it doesn't exist.

        Args:
            name: Name of the folder to find or create.
            parent_id: ID of the parent folder.

        Returns:
            ID of the found or created folder.
        """
        # Check if folder exists
        folder_id = self.find_folder(parent_id, name)

        # Create folder if it doesn't exist
        if not folder_id:
            folder_id = self.create_folder(parent_id, name)

        return folder_id

    def download_file(self, file_id: str, output_path: str) -> None:
        """Download a file from Google Drive.

        Args:
            file_id: ID of the file to download.
            output_path: Path where the file should be saved.
        """
        # Prepare parameters
        params = {"fileId": file_id}

        # Add shared drive support if applicable
        if self.shared_drive_id:
            params["supportsAllDrives"] = True

        request = self.service.files().get_media(**params)

        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with open(output_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

    def upload_file(self, file_path: str, parent_id: str, file_name: Optional[str] = None) -> str:
        """Upload a file to Google Drive.

        Args:
            file_path: Path to the file to upload.
            parent_id: ID of the parent folder.
            file_name: Optional name for the file. If None, the original filename is used.

        Returns:
            ID of the uploaded file.
        """
        if file_name is None:
            file_name = os.path.basename(file_path)

        file_metadata = {"name": file_name, "parents": [parent_id]}

        media = MediaFileUpload(file_path, resumable=True)

        # Prepare parameters
        params = {"body": file_metadata, "media_body": media, "fields": "id"}

        # Add shared drive support if applicable
        if self.shared_drive_id:
            params["supportsAllDrives"] = True

        file = self.service.files().create(**params).execute()
        logger.info(f"Uploaded file '{file_name}' with ID: {file.get('id')}")

        return file.get("id")

    def check_file_exists(self, file_name: str, parent_id: str) -> Optional[str]:
        """Check if a file exists in a folder.

        Args:
            file_name: Name of the file to check.
            parent_id: ID of the parent folder.

        Returns:
            ID of the file if it exists, None otherwise.
        """
        # Prepare query parameters
        params = {
            "q": f"name='{file_name}' and '{parent_id}' in parents and trashed=false",
            "spaces": "drive",
            "fields": "files(id)",
        }

        # Add shared drive parameters if applicable
        if self.shared_drive_id:
            params.update(
                {
                    "corpora": "drive",
                    "driveId": self.shared_drive_id,
                    "includeItemsFromAllDrives": True,
                    "supportsAllDrives": True,
                }
            )

        response = self.service.files().list(**params).execute()
        files = response.get("files", [])

        if files:
            return files[0].get("id")
        else:
            return None

    def process_image(self, input_path: str, output_path: str, max_size_kb: int = 100) -> None:
        """Process an image to convert it to PNG and reduce its size.

        Args:
            input_path: Path to the input image.
            output_path: Path where the processed image should be saved.
            max_size_kb: Maximum size of the output image in KB.
        """
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with Image.open(input_path) as img:
            # Convert to RGB if needed (for PNG conversion)
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Save as PNG with initial quality
            img.save(output_path, "PNG", optimize=True)

            # Check size and reduce quality if needed
            file_size_kb = os.path.getsize(output_path) / 1024

            if file_size_kb > max_size_kb:
                # Reduce size by scaling down the image
                scale_factor = 0.9  # Start with 90% of original size

                while file_size_kb > max_size_kb and scale_factor > 0.1:
                    new_width = int(img.width * scale_factor)
                    new_height = int(img.height * scale_factor)
                    resized_img = img.resize((new_width, new_height), Image.LANCZOS)

                    resized_img.save(output_path, "PNG", optimize=True)

                    file_size_kb = os.path.getsize(output_path) / 1024
                    scale_factor -= 0.1

                logger.info(f"Image resized to {file_size_kb:.2f}KB")

    def create_folder_path(self, folder_path: Union[str, List[str]], parent_id: str) -> str:
        """Create a path of nested folders in Google Drive.

        Args:
            folder_path: Path of folders to create. Can be a string with '/' separators or a list of folder names.
            parent_id: ID of the parent folder where the path should start.

        Returns:
            ID of the deepest created folder.
        """
        if isinstance(folder_path, str):
            # Split the path into folder names, filtering out empty strings
            folders = [f for f in folder_path.split("/") if f]
        else:
            folders = folder_path

        current_id = parent_id
        for folder in folders:
            current_id = self.find_or_create_folder(folder, current_id)

        return current_id
