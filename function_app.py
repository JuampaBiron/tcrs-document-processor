import azure.functions as func
import logging
import json
import time
from typing import Dict, Any
from datetime import datetime
from pydantic import ValidationError

# Import business logic components
from src.processors.pdf_processor import PDFProcessor
from src.processors.tiff_converter import TIFFConverter
from src.storage.blob_client import BlobStorageClient
from src.api.tcrs_client import TCRSApiClient
from src.models.request_models import DocumentProcessingRequest, ProcessingResult
from src.utils.logging_config import setup_logging, get_contextual_logger, log_performance, log_error_with_context
from src.utils.validators import sanitize_error_message

# Initialize Azure Functions app
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# Setup logging
setup_logging()


@app.route(route="process-documents", methods=["POST"])
async def process_documents(req: func.HttpRequest) -> func.HttpResponse:
    """
    Hybrid HTTP trigger for document processing.
    Triggered by: 1) Approval action, 2) Manual retry button
    Updates documentsGenerationTable status throughout process.
    """
    start_time = time.time()
    request_data = None
    request_id = "unknown"
    logger = logging.getLogger(__name__)

    try:
        # 1. Parse and validate input
        try:
            raw_body = req.get_body()
            if not raw_body:
                raise ValueError("Request body is empty")

            request_data = DocumentProcessingRequest.parse_raw(raw_body)
            request_id = request_data.requestId

            # Get contextual logger with request ID
            logger = get_contextual_logger(__name__, request_id)
            logger.info(f"Starting document processing for request {request_id} (retry: {request_data.isRetry})")

        except ValidationError as e:
            logger.error(f"Validation error: {str(e)}")
            return create_error_response(None, "Invalid request format", str(e), 400)
        except Exception as e:
            logger.error(f"Error parsing request: {str(e)}")
            return create_error_response(None, "Failed to parse request", str(e), 400)

        # Initialize clients
        tcrs_client = TCRSApiClient()
        blob_client = BlobStorageClient()
        pdf_processor = PDFProcessor()
        tiff_converter = TIFFConverter()

        # 2. Update status to 'processing'
        try:
            await tcrs_client.update_generation_status(request_id, 'processing')
            logger.info("Updated status to 'processing'")
        except Exception as e:
            logger.warning(f"Failed to update status to processing: {str(e)}")

        # 3. Fetch complete data from TCRS API
        logger.info("Fetching complete request data from TCRS API")
        complete_data = await tcrs_client.get_request_data(request_id)
        logger.info(f"Retrieved complete data for request {request_id}")

        # 4. Process documents workflow
        result = await process_documents_workflow(
            request_data, complete_data, pdf_processor, tiff_converter, blob_client, logger
        )

        # 5. Update status to 'completed' with file URLs
        processing_time_ms = int((time.time() - start_time) * 1000)
        file_urls = {
            "consolidatedPdf": result["generatedFiles"]["consolidatedPdf"],
            "tiffImage": result["generatedFiles"]["tiffImage"]
        }

        await tcrs_client.update_generation_status(
            request_id, 'completed', file_urls, processing_time_ms
        )

        logger.info(f"Document processing completed successfully for {request_id}")
        log_performance(logger, "document_processing", processing_time_ms, request_id)

        return create_success_response(request_data, result, processing_time_ms)

    except Exception as e:
        processing_time_ms = int((time.time() - start_time) * 1000)
        log_error_with_context(logger, e, "document_processing", request_id)

        # Update status to 'failed' for manual retry via UI
        if request_data:
            try:
                tcrs_client = TCRSApiClient()
                await tcrs_client.update_generation_status(
                    request_id, 'failed', None, processing_time_ms, sanitize_error_message(str(e))
                )
            except Exception as status_error:
                logger.error(f"Failed to update error status: {str(status_error)}")

        return create_error_response(request_data, "Internal processing error", str(e), 500)


async def process_documents_workflow(request_data, complete_data, pdf_processor, tiff_converter, blob_client, logger):
    """Complete document processing workflow"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        request_id = request_data.requestId

        # Extract folder from original invoice URL
        folder = blob_client.extract_folder_from_url(complete_data.invoicePdfUrl)
        logger.info(f"Using folder: '{folder}' for generated documents")

        # 1. Process PDF (download, generate signature, merge)
        logger.info("Starting PDF processing")
        consolidated_pdf = await pdf_processor.process_documents(request_data, complete_data)
        logger.info(f"PDF processing completed ({len(consolidated_pdf)} bytes)")

        # 2. Convert to TIFF
        logger.info("Starting TIFF conversion")
        tiff_data = tiff_converter.convert_pdf_to_tiff(consolidated_pdf)

        # Validate TIFF quality
        if not tiff_converter.validate_tiff_quality(tiff_data):
            logger.warning("TIFF quality validation failed, but continuing")

        logger.info(f"TIFF conversion completed ({len(tiff_data)} bytes)")

        # 3. Upload to blob storage
        logger.info("Uploading documents to blob storage")

        consolidated_pdf_url = await blob_client.upload_consolidated_pdf(
            consolidated_pdf, request_id, timestamp, folder
        )

        tiff_image_url = await blob_client.upload_tiff_image(
            tiff_data, request_id, timestamp, folder
        )

        logger.info("Document uploads completed successfully")

        # Prepare result
        result = {
            "success": True,
            "requestId": request_id,
            "generatedFiles": {
                "consolidatedPdf": consolidated_pdf_url,
                "tiffImage": tiff_image_url
            },
            "processedAt": datetime.utcnow().isoformat() + "Z",
            "isRetry": request_data.isRetry,
            "folder": folder,
            "status": "completed"
        }

        return result

    except Exception as e:
        logger.error(f"Error in document processing workflow: {str(e)}")
        raise


def create_success_response(request_data: DocumentProcessingRequest,
                          result: Dict[str, Any], processing_time_ms: int) -> func.HttpResponse:
    """Create standardized success response"""
    response_body = {
        "success": True,
        "requestId": result["requestId"],
        "generatedFiles": result["generatedFiles"],
        "processedAt": result["processedAt"],
        "processingTimeMs": processing_time_ms,
        "isRetry": result["isRetry"],
        "folder": result["folder"],
        "status": result["status"]
    }

    return func.HttpResponse(
        json.dumps(response_body),
        status_code=200,
        mimetype="application/json"
    )


def create_error_response(request_data, error_message: str,
                         details: str, status_code: int) -> func.HttpResponse:
    """Create standardized error response"""
    request_id = request_data.requestId if request_data else "unknown"

    response_body = {
        "success": False,
        "error": sanitize_error_message(error_message),
        "requestId": request_id,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    # Add details for validation errors (400)
    if status_code == 400:
        response_body["details"] = sanitize_error_message(details)

    return func.HttpResponse(
        json.dumps(response_body),
        status_code=status_code,
        mimetype="application/json"
    )


# Health check endpoint (optional, for monitoring)
@app.route(route="health", methods=["GET"])
async def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint"""
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "tcrs-document-processor"
        }),
        status_code=200,
        mimetype="application/json"
    )