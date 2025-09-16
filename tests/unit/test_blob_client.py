import pytest
from unittest.mock import Mock, patch
from src.storage.blob_client import BlobStorageClient


@pytest.fixture
def mock_blob_service_client():
    """Mock Azure BlobServiceClient"""
    with patch('src.storage.blob_client.BlobServiceClient') as mock_client:
        yield mock_client


class TestBlobStorageClient:
    """Test cases for Blob Storage client"""

    @patch.dict('os.environ', {
        'AZURE_STORAGE_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test==;EndpointSuffix=core.windows.net',
        'BLOB_CONTAINER_NAME': 'test-container'
    })
    def test_init_success(self, mock_blob_service_client):
        """Test successful blob client initialization"""
        client = BlobStorageClient()

        assert client.container_name == 'test-container'
        mock_blob_service_client.from_connection_string.assert_called_once()

    def test_init_missing_connection_string(self):
        """Test blob client initialization with missing connection string"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                BlobStorageClient()

            assert "AZURE_STORAGE_CONNECTION_STRING must be set" in str(exc_info.value)

    @patch.dict('os.environ', {
        'AZURE_STORAGE_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test==;EndpointSuffix=core.windows.net',
        'BLOB_CONTAINER_NAME': 'test-container'
    })
    @pytest.mark.asyncio
    async def test_upload_document_success(self, mock_blob_service_client):
        """Test successful document upload"""
        # Setup mocks
        mock_blob_client = Mock()
        mock_blob_client.url = "https://test.blob.core.windows.net/container/test.pdf"
        mock_blob_client.upload_blob = Mock()

        mock_service = Mock()
        mock_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_client.from_connection_string.return_value = mock_service

        client = BlobStorageClient()
        test_data = b"test file content"

        result = await client.upload_document(test_data, "test.pdf", "application/pdf")

        assert result == "https://test.blob.core.windows.net/container/test.pdf"
        mock_service.get_blob_client.assert_called_once()
        mock_blob_client.upload_blob.assert_called_once()

    @patch.dict('os.environ', {
        'AZURE_STORAGE_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test==;EndpointSuffix=core.windows.net',
        'BLOB_CONTAINER_NAME': 'test-container'
    })
    @pytest.mark.asyncio
    async def test_upload_document_failure(self, mock_blob_service_client):
        """Test document upload failure"""
        from azure.core.exceptions import AzureError

        # Setup mocks
        mock_blob_client = Mock()
        mock_blob_client.upload_blob.side_effect = AzureError("Upload failed")

        mock_service = Mock()
        mock_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_client.from_connection_string.return_value = mock_service

        client = BlobStorageClient()
        test_data = b"test file content"

        with pytest.raises(Exception) as exc_info:
            await client.upload_document(test_data, "test.pdf", "application/pdf")

        assert "Failed to upload document to blob storage" in str(exc_info.value)

    def test_extract_folder_from_url_with_folder(self):
        """Test extracting folder from blob URL with folder structure"""
        with patch.dict('os.environ', {
            'AZURE_STORAGE_CONNECTION_STRING': 'test',
            'BLOB_CONTAINER_NAME': 'test-container'
        }):
            client = BlobStorageClient()

            url = "https://storage.blob.core.windows.net/container/company/branch/2024/12/invoice.pdf"
            folder = client.extract_folder_from_url(url)

            assert folder == "company/branch/2024/12/"

    def test_extract_folder_from_url_without_folder(self):
        """Test extracting folder from blob URL without folder structure"""
        with patch.dict('os.environ', {
            'AZURE_STORAGE_CONNECTION_STRING': 'test',
            'BLOB_CONTAINER_NAME': 'test-container'
        }):
            client = BlobStorageClient()

            url = "https://storage.blob.core.windows.net/container/invoice.pdf"
            folder = client.extract_folder_from_url(url)

            assert folder == ""

    def test_extract_folder_from_invalid_url(self):
        """Test extracting folder from invalid URL"""
        with patch.dict('os.environ', {
            'AZURE_STORAGE_CONNECTION_STRING': 'test',
            'BLOB_CONTAINER_NAME': 'test-container'
        }):
            client = BlobStorageClient()

            url = "not-a-valid-url"
            folder = client.extract_folder_from_url(url)

            assert folder == ""

    def test_generate_blob_name_consolidated_pdf(self):
        """Test blob name generation for consolidated PDF"""
        with patch.dict('os.environ', {
            'AZURE_STORAGE_CONNECTION_STRING': 'test',
            'BLOB_CONTAINER_NAME': 'test-container'
        }):
            client = BlobStorageClient()

            blob_name = client.generate_blob_name("202412150001", "consolidated_pdf", "20241215_103215")

            assert blob_name == "202412150001_consolidated_20241215_103215.pdf"

    def test_generate_blob_name_tiff_image(self):
        """Test blob name generation for TIFF image"""
        with patch.dict('os.environ', {
            'AZURE_STORAGE_CONNECTION_STRING': 'test',
            'BLOB_CONTAINER_NAME': 'test-container'
        }):
            client = BlobStorageClient()

            blob_name = client.generate_blob_name("202412150001", "tiff_image", "20241215_103215")

            assert blob_name == "202412150001_document_20241215_103215.tiff"

    def test_generate_blob_name_with_folder(self):
        """Test blob name generation with folder"""
        with patch.dict('os.environ', {
            'AZURE_STORAGE_CONNECTION_STRING': 'test',
            'BLOB_CONTAINER_NAME': 'test-container'
        }):
            client = BlobStorageClient()

            blob_name = client.generate_blob_name(
                "202412150001", "consolidated_pdf", "20241215_103215", "company/branch/2024/12"
            )

            assert blob_name == "company/branch/2024/12/202412150001_consolidated_20241215_103215.pdf"

    def test_generate_blob_name_invalid_type(self):
        """Test blob name generation with invalid file type"""
        with patch.dict('os.environ', {
            'AZURE_STORAGE_CONNECTION_STRING': 'test',
            'BLOB_CONTAINER_NAME': 'test-container'
        }):
            client = BlobStorageClient()

            with pytest.raises(ValueError) as exc_info:
                client.generate_blob_name("202412150001", "invalid_type", "20241215_103215")

            assert "Unknown file type" in str(exc_info.value)

    @patch.dict('os.environ', {
        'AZURE_STORAGE_CONNECTION_STRING': 'test',
        'BLOB_CONTAINER_NAME': 'test-container'
    })
    @pytest.mark.asyncio
    async def test_upload_consolidated_pdf(self, mock_blob_service_client):
        """Test consolidated PDF upload helper method"""
        # Setup mocks
        mock_blob_client = Mock()
        mock_blob_client.url = "https://test.blob.core.windows.net/container/test.pdf"
        mock_blob_client.upload_blob = Mock()

        mock_service = Mock()
        mock_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_client.from_connection_string.return_value = mock_service

        client = BlobStorageClient()
        test_data = b"PDF content"

        result = await client.upload_consolidated_pdf(test_data, "202412150001", "20241215_103215", "test/")

        assert result == "https://test.blob.core.windows.net/container/test.pdf"

    @patch.dict('os.environ', {
        'AZURE_STORAGE_CONNECTION_STRING': 'test',
        'BLOB_CONTAINER_NAME': 'test-container'
    })
    @pytest.mark.asyncio
    async def test_upload_tiff_image(self, mock_blob_service_client):
        """Test TIFF image upload helper method"""
        # Setup mocks
        mock_blob_client = Mock()
        mock_blob_client.url = "https://test.blob.core.windows.net/container/test.tiff"
        mock_blob_client.upload_blob = Mock()

        mock_service = Mock()
        mock_service.get_blob_client.return_value = mock_blob_client
        mock_blob_service_client.from_connection_string.return_value = mock_service

        client = BlobStorageClient()
        test_data = b"TIFF content"

        result = await client.upload_tiff_image(test_data, "202412150001", "20241215_103215", "test/")

        assert result == "https://test.blob.core.windows.net/container/test.tiff"