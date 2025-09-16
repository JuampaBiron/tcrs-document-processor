from azure.storage.blob import BlobServiceClient, ContentSettings, generate_blob_sas, BlobSasPermissions
from azure.core.exceptions import AzureError
import os
import logging
from typing import Optional, Dict
from urllib.parse import urlparse
from datetime import datetime, timedelta


class BlobStorageClient:
    """Azure Blob Storage client for document uploads"""

    def __init__(self):
        self.connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self.account_name = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
        self.account_key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
        self.container_name = os.environ.get("BLOB_CONTAINER_NAME", "tcrs-documents")

        if not self.connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING must be set")

        if not self.account_name or not self.account_key:
            raise ValueError("AZURE_STORAGE_ACCOUNT_NAME and AZURE_STORAGE_ACCOUNT_KEY must be set for SAS generation")

        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        except Exception as e:
            logging.error(f"Failed to initialize BlobServiceClient: {str(e)}")
            raise

    async def upload_document(self, file_data: bytes, file_name: str, content_type: str) -> str:
        """Upload processed document to blob storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=file_name
            )

            # Upload with content settings and extended timeout
            blob_client.upload_blob(
                data=file_data,
                content_settings=ContentSettings(content_type=content_type),
                overwrite=True,
                timeout=300  # 5 minutes timeout for large files
            )

            # Generate SAS URL with read permissions valid for 1 year
            sas_url = self.generate_sas_url(file_name)
            logging.info(f"Successfully uploaded {file_name} to blob storage with SAS URL")
            return sas_url

        except AzureError as e:
            logging.error(f"Azure error uploading {file_name}: {str(e)}")
            raise Exception(f"Failed to upload document to blob storage: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error uploading {file_name}: {str(e)}")
            raise

    def extract_folder_from_url(self, blob_url: str) -> str:
        """Extract folder path from original invoice PDF URL"""
        try:
            parsed_url = urlparse(blob_url)
            # Extract path without container name and file name
            path_parts = parsed_url.path.strip('/').split('/')

            if len(path_parts) >= 2:
                # Remove container name (first part) and filename (last part)
                folder_parts = path_parts[1:-1]
                return '/'.join(folder_parts) + '/' if folder_parts else ''

            return ''

        except Exception as e:
            logging.warning(f"Failed to extract folder from URL {blob_url}: {str(e)}")
            return ''

    def generate_blob_name(self, request_id: str, file_type: str, timestamp: str, folder: str = "") -> str:
        """Generate blob name following the mandatory naming convention"""
        if file_type == "consolidated_pdf":
            file_name = f"{request_id}_consolidated_{timestamp}.pdf"
        elif file_type == "tiff_image":
            file_name = f"{request_id}_document_{timestamp}.tiff"
        else:
            raise ValueError(f"Unknown file type: {file_type}")

        # Include folder path if provided
        if folder and not folder.endswith('/'):
            folder += '/'

        return f"{folder}{file_name}" if folder else file_name

    def generate_sas_url(self, blob_name: str, expiry_hours: int = 8760) -> str:
        """Generate SAS URL for blob with read permissions

        Args:
            blob_name: Name of the blob
            expiry_hours: Hours until SAS token expires (default: 1 year)

        Returns:
            Full SAS URL for the blob
        """
        try:
            # Set expiry time
            expiry_time = datetime.utcnow() + timedelta(hours=expiry_hours)

            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=self.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=expiry_time
            )

            # Construct full SAS URL
            sas_url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{sas_token}"

            logging.info(f"Generated SAS URL for {blob_name} (expires: {expiry_time})")
            return sas_url

        except Exception as e:
            logging.error(f"Failed to generate SAS URL for {blob_name}: {str(e)}")
            # Fallback to regular blob URL
            return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}"

    def generate_sas_url_for_existing_blob(self, blob_url: str) -> str:
        """Generate SAS URL for an existing blob from its public URL

        Args:
            blob_url: Public blob URL (e.g. https://account.blob.core.windows.net/container/path/file.pdf)

        Returns:
            SAS URL with read permissions
        """
        try:
            # Extract blob name from URL
            # URL format: https://account.blob.core.windows.net/container/path/to/file.pdf
            blob_name = blob_url.split(f"/{self.container_name}/")[1]

            logging.info(f"Extracting blob name '{blob_name}' from URL: {blob_url}")

            # Generate SAS URL using the existing method
            return self.generate_sas_url(blob_name)

        except Exception as e:
            logging.error(f"Failed to generate SAS URL for existing blob {blob_url}: {str(e)}")
            # Return original URL as fallback
            return blob_url

    async def upload_consolidated_pdf(self, pdf_data: bytes, request_id: str,
                                    timestamp: str, folder: str = "") -> str:
        """Upload consolidated PDF with proper naming"""
        blob_name = self.generate_blob_name(request_id, "consolidated_pdf", timestamp, folder)
        return await self.upload_document(pdf_data, blob_name, "application/pdf")

    async def upload_tiff_image(self, tiff_data: bytes, request_id: str,
                               timestamp: str, folder: str = "") -> str:
        """Upload TIFF image with proper naming"""
        blob_name = self.generate_blob_name(request_id, "tiff_image", timestamp, folder)
        return await self.upload_document(tiff_data, blob_name, "image/tiff")