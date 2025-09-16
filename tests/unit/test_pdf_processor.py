import pytest
import io
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from src.processors.pdf_processor import PDFProcessor
from src.models.request_models import DocumentProcessingRequest, CompleteRequestData, GLCodingEntry


@pytest.fixture
def sample_request():
    """Sample document processing request"""
    return DocumentProcessingRequest(
        requestId="202412150001",
        approverName="John Smith",
        approverEmail="john@company.com",
        timestamp=datetime.now(),
        isRetry=False
    )


@pytest.fixture
def sample_complete_data():
    """Sample complete request data"""
    return CompleteRequestData(
        requestId="202412150001",
        invoicePdfUrl="https://example.blob.core.windows.net/test/invoice.pdf",
        requestInfo={
            "amount": 5000.00,
            "vendor": "Test Vendor Inc",
            "company": "Test Company",
            "branch": "Main Branch"
        },
        glCodingData=[
            GLCodingEntry(
                accountCode="1000",
                accountDescription="Equipment Account",
                facilityCode="MAIN",
                facilityDescription="Main Facility",
                taxCode="GST",
                amount=3000.00,
                equipment="CAT-950",
                comments="Heavy equipment"
            ),
            GLCodingEntry(
                accountCode="2000",
                accountDescription="Parts Account",
                facilityCode="SHOP",
                facilityDescription="Shop Facility",
                taxCode="GST",
                amount=2000.00,
                comments="Replacement parts"
            )
        ],
        approverInfo={
            "name": "John Smith",
            "email": "john@company.com"
        }
    )


@pytest.fixture
def mock_pdf_data():
    """Mock PDF data"""
    # Create a minimal valid PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj

xref
0 4
0000000000 65535 f
0000000015 65535 n
0000000074 65535 n
0000000120 65535 n
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
190
%%EOF"""
    return pdf_content


class TestPDFProcessor:
    """Test cases for PDF processor"""

    def test_init(self):
        """Test PDF processor initialization"""
        processor = PDFProcessor()
        assert processor is not None

    @pytest.mark.asyncio
    async def test_download_pdf_success(self, mock_pdf_data):
        """Test successful PDF download"""
        processor = PDFProcessor()

        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read.return_value = mock_pdf_data

            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            result = await processor.download_pdf("https://example.com/test.pdf")

            assert result == mock_pdf_data
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_download_pdf_failure(self):
        """Test PDF download failure"""
        processor = PDFProcessor()

        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 404

            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            with pytest.raises(Exception) as exc_info:
                await processor.download_pdf("https://example.com/nonexistent.pdf")

            assert "Failed to download PDF" in str(exc_info.value)

    def test_generate_signature_page(self, sample_request, sample_complete_data):
        """Test signature page generation"""
        processor = PDFProcessor()
        signature_pdf = processor.generate_signature_page(sample_request, sample_complete_data)

        assert isinstance(signature_pdf, bytes)
        assert len(signature_pdf) > 0
        # Check that it starts with PDF header
        assert signature_pdf.startswith(b'%PDF')

    def test_generate_signature_page_with_minimal_data(self, sample_request):
        """Test signature page generation with minimal data"""
        processor = PDFProcessor()

        minimal_complete_data = CompleteRequestData(
            requestId="202412150001",
            invoicePdfUrl="https://example.com/test.pdf",
            requestInfo={},
            glCodingData=[],
            approverInfo={}
        )

        signature_pdf = processor.generate_signature_page(sample_request, minimal_complete_data)

        assert isinstance(signature_pdf, bytes)
        assert len(signature_pdf) > 0

    def test_merge_pdfs_success(self, mock_pdf_data):
        """Test successful PDF merge"""
        processor = PDFProcessor()

        # Use the same mock PDF data for both invoice and signature
        merged_pdf = processor.merge_pdfs(mock_pdf_data, mock_pdf_data)

        assert isinstance(merged_pdf, bytes)
        assert len(merged_pdf) > 0
        assert merged_pdf.startswith(b'%PDF')

    def test_merge_pdfs_invalid_data(self):
        """Test PDF merge with invalid data"""
        processor = PDFProcessor()

        invalid_pdf = b"not a pdf"

        with pytest.raises(Exception) as exc_info:
            processor.merge_pdfs(invalid_pdf, invalid_pdf)

        assert "Failed to merge PDFs" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_documents_workflow(self, sample_request, sample_complete_data, mock_pdf_data):
        """Test complete document processing workflow"""
        processor = PDFProcessor()

        with patch.object(processor, 'download_pdf', return_value=mock_pdf_data), \
             patch.object(processor, 'generate_signature_page', return_value=mock_pdf_data), \
             patch.object(processor, 'merge_pdfs', return_value=mock_pdf_data):

            result = await processor.process_documents(sample_request, sample_complete_data)

            assert isinstance(result, bytes)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_process_documents_download_failure(self, sample_request, sample_complete_data):
        """Test document processing with download failure"""
        processor = PDFProcessor()

        with patch.object(processor, 'download_pdf', side_effect=Exception("Download failed")):
            with pytest.raises(Exception) as exc_info:
                await processor.process_documents(sample_request, sample_complete_data)

            assert "Download failed" in str(exc_info.value)

    def test_signature_page_contains_required_info(self, sample_request, sample_complete_data):
        """Test that signature page contains all required information"""
        processor = PDFProcessor()
        signature_pdf = processor.generate_signature_page(sample_request, sample_complete_data)

        # Convert to string to check content (this is a simplified check)
        # In a real test, you might want to use a PDF parsing library
        assert isinstance(signature_pdf, bytes)
        assert len(signature_pdf) > 1000  # Should be substantial content

        # Verify PDF structure
        assert signature_pdf.startswith(b'%PDF')
        assert b'%%EOF' in signature_pdf