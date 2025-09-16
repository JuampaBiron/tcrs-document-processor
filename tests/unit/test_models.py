import pytest
from datetime import datetime
from pydantic import ValidationError
from src.models.request_models import (
    GLCodingEntry, DocumentProcessingRequest, CompleteRequestData,
    DocumentGenerationStatus, ProcessingResult
)


class TestGLCodingEntry:
    """Test cases for GL Coding Entry model"""

    def test_valid_gl_coding_entry(self):
        """Test valid GL coding entry"""
        entry = GLCodingEntry(
            accountCode="1000",
            accountDescription="Equipment Account",
            facilityCode="MAIN",
            facilityDescription="Main Facility",
            taxCode="GST",
            amount=1500.00,
            equipment="CAT-950",
            comments="Heavy equipment purchase"
        )

        assert entry.accountCode == "1000"
        assert entry.amount == 1500.00
        assert entry.equipment == "CAT-950"

    def test_gl_coding_entry_without_optional_fields(self):
        """Test GL coding entry without optional fields"""
        entry = GLCodingEntry(
            accountCode="2000",
            accountDescription="Parts Account",
            facilityCode="SHOP",
            facilityDescription="Shop Facility",
            taxCode="GST",
            amount=500.00
        )

        assert entry.accountCode == "2000"
        assert entry.equipment is None
        assert entry.comments is None

    def test_gl_coding_entry_invalid_amount(self):
        """Test GL coding entry with invalid amount"""
        with pytest.raises(ValidationError) as exc_info:
            GLCodingEntry(
                accountCode="1000",
                accountDescription="Equipment Account",
                facilityCode="MAIN",
                facilityDescription="Main Facility",
                taxCode="GST",
                amount=0  # Invalid: must be greater than 0
            )

        assert "ensure this value is greater than 0" in str(exc_info.value)

    def test_gl_coding_entry_empty_required_fields(self):
        """Test GL coding entry with empty required fields"""
        with pytest.raises(ValidationError) as exc_info:
            GLCodingEntry(
                accountCode="",  # Invalid: empty string
                accountDescription="Equipment Account",
                facilityCode="MAIN",
                facilityDescription="Main Facility",
                taxCode="GST",
                amount=1500.00
            )

        assert "ensure this value has at least 1 characters" in str(exc_info.value)


class TestDocumentProcessingRequest:
    """Test cases for Document Processing Request model"""

    def test_valid_document_processing_request(self):
        """Test valid document processing request"""
        request = DocumentProcessingRequest(
            requestId="202412150001",
            approverName="John Smith",
            approverEmail="john@company.com",
            timestamp=datetime.now(),
            isRetry=False
        )

        assert request.requestId == "202412150001"
        assert request.approverName == "John Smith"
        assert request.isRetry is False

    def test_document_processing_request_retry_default(self):
        """Test document processing request with default retry value"""
        request = DocumentProcessingRequest(
            requestId="202412150001",
            approverName="John Smith",
            approverEmail="john@company.com",
            timestamp=datetime.now()
        )

        assert request.isRetry is False

    def test_invalid_request_id_format(self):
        """Test invalid request ID format"""
        with pytest.raises(ValidationError) as exc_info:
            DocumentProcessingRequest(
                requestId="invalid123",  # Invalid: not 12 digits
                approverName="John Smith",
                approverEmail="john@company.com",
                timestamp=datetime.now()
            )

        assert "string does not match expected pattern" in str(exc_info.value)

    def test_invalid_email_format(self):
        """Test invalid email format"""
        with pytest.raises(ValidationError) as exc_info:
            DocumentProcessingRequest(
                requestId="202412150001",
                approverName="John Smith",
                approverEmail="invalid-email",  # Invalid email format
                timestamp=datetime.now()
            )

        assert "string does not match expected pattern" in str(exc_info.value)

    def test_empty_approver_name(self):
        """Test empty approver name"""
        with pytest.raises(ValidationError) as exc_info:
            DocumentProcessingRequest(
                requestId="202412150001",
                approverName="",  # Invalid: empty string
                approverEmail="john@company.com",
                timestamp=datetime.now()
            )

        assert "ensure this value has at least 1 characters" in str(exc_info.value)


class TestCompleteRequestData:
    """Test cases for Complete Request Data model"""

    def test_valid_complete_request_data(self):
        """Test valid complete request data"""
        gl_entries = [
            GLCodingEntry(
                accountCode="1000",
                accountDescription="Equipment Account",
                facilityCode="MAIN",
                facilityDescription="Main Facility",
                taxCode="GST",
                amount=1500.00
            )
        ]

        complete_data = CompleteRequestData(
            requestId="202412150001",
            invoicePdfUrl="https://example.blob.core.windows.net/container/invoice.pdf",
            requestInfo={"amount": 1500.00, "vendor": "Test Vendor"},
            glCodingData=gl_entries,
            approverInfo={"name": "John Smith", "email": "john@company.com"}
        )

        assert complete_data.requestId == "202412150001"
        assert len(complete_data.glCodingData) == 1
        assert complete_data.requestInfo["vendor"] == "Test Vendor"

    def test_complete_request_data_empty_gl_coding(self):
        """Test complete request data with empty GL coding list"""
        complete_data = CompleteRequestData(
            requestId="202412150001",
            invoicePdfUrl="https://example.blob.core.windows.net/container/invoice.pdf",
            requestInfo={"amount": 1500.00, "vendor": "Test Vendor"},
            glCodingData=[],  # Empty list is valid
            approverInfo={"name": "John Smith", "email": "john@company.com"}
        )

        assert len(complete_data.glCodingData) == 0


class TestDocumentGenerationStatus:
    """Test cases for Document Generation Status model"""

    def test_valid_document_generation_status(self):
        """Test valid document generation status"""
        status = DocumentGenerationStatus(
            requestId="202412150001",
            status="completed",
            consolidatedPdfUrl="https://example.com/consolidated.pdf",
            tiffImageUrl="https://example.com/document.tiff",
            generatedAt=datetime.now(),
            processingTimeMs=2500
        )

        assert status.requestId == "202412150001"
        assert status.status == "completed"
        assert status.processingTimeMs == 2500

    def test_document_generation_status_minimal(self):
        """Test document generation status with minimal fields"""
        status = DocumentGenerationStatus(
            requestId="202412150001",
            status="pending"
        )

        assert status.requestId == "202412150001"
        assert status.status == "pending"
        assert status.consolidatedPdfUrl is None
        assert status.processingTimeMs is None

    def test_document_generation_status_failed(self):
        """Test document generation status for failed processing"""
        status = DocumentGenerationStatus(
            requestId="202412150001",
            status="failed",
            errorMessage="Processing failed due to invalid PDF",
            processingTimeMs=1200
        )

        assert status.status == "failed"
        assert "invalid PDF" in status.errorMessage
        assert status.consolidatedPdfUrl is None


class TestProcessingResult:
    """Test cases for Processing Result model"""

    def test_valid_processing_result(self):
        """Test valid processing result"""
        result = ProcessingResult(
            success=True,
            requestId="202412150001",
            generatedFiles={
                "consolidatedPdf": "https://example.com/consolidated.pdf",
                "tiffImage": "https://example.com/document.tiff"
            },
            processedAt="2024-12-15T10:32:15Z",
            processingTimeMs=2500,
            isRetry=False,
            folder="company/branch/2024/12/",
            status="completed"
        )

        assert result.success is True
        assert result.requestId == "202412150001"
        assert result.processingTimeMs == 2500
        assert "consolidatedPdf" in result.generatedFiles

    def test_processing_result_failure(self):
        """Test processing result for failure case"""
        result = ProcessingResult(
            success=False,
            requestId="202412150001",
            generatedFiles={},
            processedAt="2024-12-15T10:32:15Z",
            processingTimeMs=1200,
            isRetry=True,
            folder="",
            status="failed"
        )

        assert result.success is False
        assert result.isRetry is True
        assert result.status == "failed"
        assert len(result.generatedFiles) == 0