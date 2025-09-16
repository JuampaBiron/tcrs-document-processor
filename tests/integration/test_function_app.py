import pytest
import json
from unittest.mock import patch, Mock, AsyncMock
import azure.functions as func
from function_app import process_documents


@pytest.fixture
def valid_request_body():
    """Valid request body for testing"""
    return {
        "requestId": "202412150001",
        "approverName": "John Smith",
        "approverEmail": "john@company.com",
        "timestamp": "2024-12-15T10:30:00Z",
        "isRetry": False
    }


@pytest.fixture
def mock_complete_data():
    """Mock complete request data from TCRS API"""
    return {
        "requestId": "202412150001",
        "invoicePdfUrl": "https://example.blob.core.windows.net/container/invoice.pdf",
        "requestInfo": {
            "amount": 5000.00,
            "vendor": "Test Vendor Inc",
            "company": "Test Company",
            "branch": "Main Branch"
        },
        "glCodingData": [
            {
                "accountCode": "1000",
                "accountDescription": "Equipment Account",
                "facilityCode": "MAIN",
                "facilityDescription": "Main Facility",
                "taxCode": "GST",
                "amount": 5000.00,
                "equipment": "CAT-950",
                "comments": "Heavy equipment"
            }
        ],
        "approverInfo": {
            "name": "John Smith",
            "email": "john@company.com"
        }
    }


class TestFunctionApp:
    """Integration tests for the Azure Function app"""

    @pytest.mark.asyncio
    @patch.dict('os.environ', {
        'TCRS_API_BASE_URL': 'https://test-api.com',
        'INTERNAL_FUNCTION_KEY': 'test-key',
        'AZURE_STORAGE_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test==;EndpointSuffix=core.windows.net',
        'BLOB_CONTAINER_NAME': 'test-container'
    })
    async def test_process_documents_success(self, valid_request_body, mock_complete_data):
        """Test successful document processing workflow"""

        # Create HTTP request
        req = func.HttpRequest(
            method='POST',
            url='http://localhost:7071/api/process-documents',
            body=json.dumps(valid_request_body).encode('utf-8'),
            headers={'content-type': 'application/json'}
        )

        # Mock all external dependencies
        with patch('src.api.tcrs_client.TCRSApiClient') as mock_tcrs_client, \
             patch('src.storage.blob_client.BlobStorageClient') as mock_blob_client, \
             patch('src.processors.pdf_processor.PDFProcessor') as mock_pdf_processor, \
             patch('src.processors.tiff_converter.TIFFConverter') as mock_tiff_converter:

            # Setup TCRS client mock
            tcrs_instance = mock_tcrs_client.return_value
            tcrs_instance.get_request_data = AsyncMock(return_value=Mock(**mock_complete_data))
            tcrs_instance.update_generation_status = AsyncMock()

            # Setup blob client mock
            blob_instance = mock_blob_client.return_value
            blob_instance.extract_folder_from_url.return_value = "company/branch/2024/12/"
            blob_instance.upload_consolidated_pdf = AsyncMock(return_value="https://example.com/consolidated.pdf")
            blob_instance.upload_tiff_image = AsyncMock(return_value="https://example.com/document.tiff")

            # Setup PDF processor mock
            pdf_instance = mock_pdf_processor.return_value
            pdf_instance.process_documents = AsyncMock(return_value=b"PDF content")

            # Setup TIFF converter mock
            tiff_instance = mock_tiff_converter.return_value
            tiff_instance.convert_pdf_to_tiff.return_value = b"TIFF content"
            tiff_instance.validate_tiff_quality.return_value = True

            # Execute the function
            response = await process_documents(req)

            # Verify response
            assert response.status_code == 200
            response_data = json.loads(response.get_body().decode('utf-8'))

            assert response_data['success'] is True
            assert response_data['requestId'] == "202412150001"
            assert 'generatedFiles' in response_data
            assert 'consolidatedPdf' in response_data['generatedFiles']
            assert 'tiffImage' in response_data['generatedFiles']

    @pytest.mark.asyncio
    async def test_process_documents_invalid_request(self):
        """Test function with invalid request body"""

        # Create HTTP request with invalid body
        req = func.HttpRequest(
            method='POST',
            url='http://localhost:7071/api/process-documents',
            body=b'invalid json',
            headers={'content-type': 'application/json'}
        )

        response = await process_documents(req)

        assert response.status_code == 400
        response_data = json.loads(response.get_body().decode('utf-8'))

        assert response_data['success'] is False
        assert 'error' in response_data

    @pytest.mark.asyncio
    async def test_process_documents_empty_body(self):
        """Test function with empty request body"""

        # Create HTTP request with empty body
        req = func.HttpRequest(
            method='POST',
            url='http://localhost:7071/api/process-documents',
            body=b'',
            headers={'content-type': 'application/json'}
        )

        response = await process_documents(req)

        assert response.status_code == 400
        response_data = json.loads(response.get_body().decode('utf-8'))

        assert response_data['success'] is False
        assert 'error' in response_data

    @pytest.mark.asyncio
    @patch.dict('os.environ', {
        'TCRS_API_BASE_URL': 'https://test-api.com',
        'INTERNAL_FUNCTION_KEY': 'test-key',
        'AZURE_STORAGE_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test==;EndpointSuffix=core.windows.net',
        'BLOB_CONTAINER_NAME': 'test-container'
    })
    async def test_process_documents_tcrs_api_failure(self, valid_request_body):
        """Test function when TCRS API call fails"""

        # Create HTTP request
        req = func.HttpRequest(
            method='POST',
            url='http://localhost:7071/api/process-documents',
            body=json.dumps(valid_request_body).encode('utf-8'),
            headers={'content-type': 'application/json'}
        )

        # Mock TCRS client to raise exception
        with patch('src.api.tcrs_client.TCRSApiClient') as mock_tcrs_client:
            tcrs_instance = mock_tcrs_client.return_value
            tcrs_instance.update_generation_status = AsyncMock()
            tcrs_instance.get_request_data = AsyncMock(side_effect=Exception("API error"))

            response = await process_documents(req)

            assert response.status_code == 500
            response_data = json.loads(response.get_body().decode('utf-8'))

            assert response_data['success'] is False
            assert response_data['requestId'] == "202412150001"

    @pytest.mark.asyncio
    @patch.dict('os.environ', {
        'TCRS_API_BASE_URL': 'https://test-api.com',
        'INTERNAL_FUNCTION_KEY': 'test-key',
        'AZURE_STORAGE_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test==;EndpointSuffix=core.windows.net',
        'BLOB_CONTAINER_NAME': 'test-container'
    })
    async def test_process_documents_pdf_processing_failure(self, valid_request_body, mock_complete_data):
        """Test function when PDF processing fails"""

        # Create HTTP request
        req = func.HttpRequest(
            method='POST',
            url='http://localhost:7071/api/process-documents',
            body=json.dumps(valid_request_body).encode('utf-8'),
            headers={'content-type': 'application/json'}
        )

        with patch('src.api.tcrs_client.TCRSApiClient') as mock_tcrs_client, \
             patch('src.storage.blob_client.BlobStorageClient') as mock_blob_client, \
             patch('src.processors.pdf_processor.PDFProcessor') as mock_pdf_processor:

            # Setup TCRS client mock
            tcrs_instance = mock_tcrs_client.return_value
            tcrs_instance.get_request_data = AsyncMock(return_value=Mock(**mock_complete_data))
            tcrs_instance.update_generation_status = AsyncMock()

            # Setup blob client mock
            blob_instance = mock_blob_client.return_value
            blob_instance.extract_folder_from_url.return_value = ""

            # Setup PDF processor mock to fail
            pdf_instance = mock_pdf_processor.return_value
            pdf_instance.process_documents = AsyncMock(side_effect=Exception("PDF processing failed"))

            response = await process_documents(req)

            assert response.status_code == 500
            response_data = json.loads(response.get_body().decode('utf-8'))

            assert response_data['success'] is False
            assert response_data['requestId'] == "202412150001"

            # Verify that status was updated to 'failed'
            tcrs_instance.update_generation_status.assert_called()
            # Check that the last call was to set status to 'failed'
            last_call_args = tcrs_instance.update_generation_status.call_args_list[-1]
            assert last_call_args[0][1] == 'failed'  # Second argument should be 'failed'


class TestHealthEndpoint:
    """Test cases for health check endpoint"""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint"""
        from function_app import health_check

        req = func.HttpRequest(
            method='GET',
            url='http://localhost:7071/api/health',
            body=b'',
            headers={}
        )

        response = await health_check(req)

        assert response.status_code == 200
        response_data = json.loads(response.get_body().decode('utf-8'))

        assert response_data['status'] == 'healthy'
        assert response_data['service'] == 'tcrs-document-processor'
        assert 'timestamp' in response_data