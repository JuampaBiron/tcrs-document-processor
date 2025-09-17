# CLAUDE.md

Este archivo proporciona guías específicas para Claude Code cuando trabaja en el proyecto Azure Function para procesamiento de documentos TCRS.

## 🚨 REGLAS CRÍTICAS (DEBE SEGUIR)

### 1. Arquitectura Azure Functions - Hybrid HTTP + Manual Retry
- **OBLIGATORIO**: Usar Azure Functions Core Tools 4.x con Python 3.11
- **FORBIDDEN**: Node.js para este proyecto - Python es OBLIGATORIO para PDF/TIFF processing
- **STRUCTURE**: Mantener separación clara entre function triggers y business logic
- **PATTERN**: Un endpoint HTTP principal `/api/process-documents` que orquesta todo el procesamiento
- **HYBRID APPROACH**: HTTP inmediato + manual retry via UI (NO timer automático)
- **DATABASE TRACKING**: Todos los estados en documentsGenerationTable para visibilidad completa

### 2. Librerías Python MANDATORIAS
```python
# PDF Processing (CORE)
PyPDF2==3.0.1              # PDF merge y manipulación
reportlab==4.0.7            # PDF generation y firma digital
Pillow==10.1.0              # TIFF conversion y image processing

# Azure SDK (REQUIRED)
azure-functions==1.18.0     # Azure Functions runtime
azure-storage-blob==12.19.0 # Blob storage operations
azure-identity==1.15.0      # Authentication

# HTTP & Validation (CORE)
aiohttp==3.9.1              # Async HTTP client para downloads
pydantic==2.7.4             # Data validation y models (compatible con langchain si existe)
```

### 3. Estructura de Archivos OBLIGATORIA
```
tcrs-document-processor/
├── function_app.py          # MAIN entry point - HTTP trigger function
├── requirements.txt         # EXACT versions listed above
├── host.json               # Azure Functions configuration
├── local.settings.json     # Local development settings (NOT committed)
├── local.settings.example.json # Template for setup
├── src/
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── pdf_processor.py      # PDF merge logic con SAS authentication
│   │   └── tiff_converter.py     # PDF to TIFF conversion optimizado
│   ├── storage/
│   │   ├── __init__.py
│   │   └── blob_client.py        # Azure Blob Storage con SAS URL generation
│   ├── api/
│   │   ├── __init__.py
│   │   └── tcrs_client.py        # TCRS API integration
│   ├── models/
│   │   ├── __init__.py
│   │   └── request_models.py     # Pydantic data models
│   └── utils/
│       ├── __init__.py
│       ├── logging_config.py     # Structured logging setup
│       ├── performance.py        # Performance tracking system
│       └── validators.py         # Input validation functions
```

### 4. Function Entry Point Pattern ACTUAL
```python
# function_app.py (MANDATORY STRUCTURE)
import azure.functions as func
import logging
import json
import time
import os
from typing import Dict, Any
from datetime import datetime
from pydantic import ValidationError

from src.processors.pdf_processor import PDFProcessor
from src.processors.tiff_converter import TIFFConverter
from src.storage.blob_client import BlobStorageClient
from src.api.tcrs_client import TCRSApiClient
from src.models.request_models import DocumentProcessingRequest, ProcessingResult
from src.utils.logging_config import setup_logging, get_contextual_logger, log_error_with_context
from src.utils.validators import sanitize_error_message
from src.utils.performance import PerformanceTracker

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

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

    # Initialize performance tracker
    perf_tracker = PerformanceTracker()

    try:
        # 1. Parse and validate input con performance tracking
        with perf_tracker.time_stage("input_validation"):
            request_data = DocumentProcessingRequest.model_validate_json(req.get_body())
            request_id = request_data.requestId
            logger = get_contextual_logger(__name__, request_id)

        # 2. Process workflow con timing detallado
        with perf_tracker.time_stage("document_processing"):
            result = await process_documents_workflow(...)

        # 3. Log performance summary
        perf_tracker.log_summary(request_id)
        result["performance"] = perf_tracker.get_performance_data()

        return create_success_response(request_data, result)

    except Exception as e:
        log_error_with_context(logger, e, "document_processing", request_id)
        return create_error_response(request_data, sanitize_error_message(str(e)))
```

### 5. SAS URL Integration MANDATORIO
```python
# src/storage/blob_client.py (ACTUAL IMPLEMENTATION)
from azure.storage.blob import BlobServiceClient, ContentSettings, generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta

class BlobStorageClient:
    def __init__(self):
        self.connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self.account_name = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
        self.account_key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
        self.container_name = os.environ.get("BLOB_CONTAINER_NAME", "invoices")

    def generate_sas_url(self, blob_name: str, expiry_hours: int = None) -> str:
        """Generate SAS URL with configurable expiry (default: 1 hour)"""
        if expiry_hours is None:
            expiry_hours = int(os.environ.get("SAS_EXPIRY_HOURS", "1"))
        expiry_time = datetime.utcnow() + timedelta(hours=expiry_hours)

        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_name=blob_name,
            account_key=self.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry_time
        )

        return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{sas_token}"

    def generate_sas_url_for_existing_blob(self, blob_url: str) -> str:
        """Generate SAS URL for existing blob from public URL"""
        blob_name = blob_url.split(f"/{self.container_name}/")[1]
        return self.generate_sas_url(blob_name)

    async def upload_document(self, file_data: bytes, file_name: str, content_type: str) -> str:
        """Upload document and return SAS URL"""
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name, blob=file_name
        )

        # Upload with extended timeout
        blob_client.upload_blob(
            data=file_data,
            content_settings=ContentSettings(content_type=content_type),
            overwrite=True,
            timeout=300  # 5 minutes for large files
        )

        # Return SAS URL instead of public URL
        return self.generate_sas_url(file_name)
```

### 6. TIFF Processing Optimizado ACTUAL
```python
# src/processors/tiff_converter.py (CURRENT OPTIMIZATIONS)
class TIFFConverter:
    def __init__(self):
        self.dpi = 120  # Optimized for large documents
        self.compression = "jpeg"  # JPEG compression for smaller files
        self.jpeg_quality = 80  # Balance quality/size
        self.max_image_width = 2000  # Prevent memory issues

    def images_to_singlepage_tiff(self, images: List[Image.Image]) -> bytes:
        """Convert images to optimized single-page TIFF"""
        combined = self.combine_images_vertically(images)
        output_buffer = io.BytesIO()

        save_kwargs = {
            "format": "TIFF",
            "compression": self.compression,
            "dpi": (self.dpi, self.dpi)
        }

        if self.compression == "jpeg":
            save_kwargs["quality"] = self.jpeg_quality

        combined.save(output_buffer, **save_kwargs)
        output_buffer.seek(0)
        tiff_data = output_buffer.getvalue()

        # Log size for optimization tracking
        logging.info(f"Generated TIFF: {len(tiff_data)/1024/1024:.2f} MB")
        return tiff_data

    def pdf_to_images(self, pdf_data: bytes) -> List[Image.Image]:
        """Convert PDF to images with automatic resizing"""
        # ... existing conversion logic ...

        # CRITICAL: Resize if too wide to prevent memory issues
        if pil_image.width > self.max_image_width:
            ratio = self.max_image_width / pil_image.width
            new_height = int(pil_image.height * ratio)
            pil_image = pil_image.resize((self.max_image_width, new_height), Image.Resampling.LANCZOS)
```

### 7. Performance Monitoring System ACTUAL
```python
# src/utils/performance.py (IMPLEMENTED)
class PerformanceTracker:
    def __init__(self):
        self.timings: Dict[str, float] = {}
        self.start_times: Dict[str, float] = {}

    @contextmanager
    def time_stage(self, stage: str):
        """Context manager for timing stages"""
        self.start_timing(stage)
        try:
            yield
        finally:
            self.end_timing(stage)

    def log_summary(self, request_id: str) -> None:
        """Log comprehensive performance summary"""
        total_time = self.get_total_time()
        logging.info(f"📊 Performance Summary for Request {request_id}")
        logging.info(f"   Total Processing Time: {total_time:.2f}s ({total_time/60:.1f}m)")

        for stage, duration in sorted(self.timings.items(), key=lambda x: x[1], reverse=True):
            percentage = (duration / total_time * 100) if total_time > 0 else 0
            logging.info(f"   {stage}: {duration:.2f}s ({percentage:.1f}%)")
```

### 8. Environment Variables ACTUALES
```json
// local.settings.json (REQUIRED CONFIGURATION)
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=stcatcrsprod;...",
    "AZURE_STORAGE_ACCOUNT_NAME": "stcatcrsprod",
    "AZURE_STORAGE_ACCOUNT_KEY": "your_account_key",
    "BLOB_CONTAINER_NAME": "invoices",
    "TCRS_API_BASE_URL": "http://localhost:3000",
    "INTERNAL_FUNCTION_KEY": "hola",
    "ALLOWED_ORIGINS": "http://localhost:3000,http://localhost:8000",
    "LOG_LEVEL": "DEBUG",
    "TESTING_MODE": "true",
    "SAVE_LOCAL_COPIES": "true"  // Debug feature
  }
}
```

## 🚫 FORBIDDEN PRACTICES (ACTUALIZADAS)

### Dependencies & Libraries
- ❌ **NO Pillow < 10.1.0** - Usar versiones recientes para stability
- ❌ **NO synchronous blob operations** - Siempre usar async con timeouts
- ❌ **NO hardcoded SAS tokens** - Generar dinámicamente
- ❌ **NO public blob URLs** - Siempre retornar SAS URLs

### Performance & Memory
- ❌ **NO DPI > 120** para documentos grandes - Causa timeouts
- ❌ **NO images > 2000px width** - Resizing automático obligatorio
- ❌ **NO LZW compression** para TIFF - JPEG es más eficiente
- ❌ **NO blocking operations** sin timeouts

### Development & Debugging
- ❌ **NO eliminar performance tracking** - Es crítico para optimization
- ❌ **NO console.log** en lugar de logging estructurado
- ❌ **NO commits** sin performance analysis

## 💡 CURRENT IMPLEMENTATION STATUS

### ✅ IMPLEMENTADO Y FUNCIONANDO
- **SAS URL Generation**: Automático para todos los archivos
- **Performance Tracking**: Sistema completo con timing detallado
- **TIFF Optimization**: 120 DPI, JPEG compression, auto-resize
- **Error Handling**: Comprehensive con retry support
- **Local Debug**: SAVE_LOCAL_COPIES para inspection
- **Async Operations**: Todo I/O es non-blocking

### 📊 PERFORMANCE BENCHMARKS ACTUALES
```
Typical Processing (11.6s total):
├── pdf_processing: 1.83s (15.9%) - Download + Generate + Merge
├── tiff_conversion: 0.61s (5.3%) - Optimized conversion
├── blob_storage_upload: 2.69s (23.3%) - SAS URL generation
├── status_updates: 0.89s (7.7%) - TCRS API calls
└── overhead: 5.58s (48.2%) - Framework + coordination
```

### 🎯 OPTIMIZATION RESULTS
- **TIFF files**: 70% smaller vs original implementation
- **Memory usage**: Controlled via max_image_width
- **Upload speed**: 5min timeout prevents failures
- **Processing time**: <12s for typical documents

## 📋 MAINTENANCE GUIDELINES

### Code Quality Standards ACTUALES
- **Type Hints**: TODOS los functions (implemented)
- **Performance Tracking**: OBLIGATORIO para new features
- **Error Sanitization**: NUNCA exponer internal errors
- **SAS URLs**: SIEMPRE en lugar de public URLs
- **Async/Await**: TODO I/O debe ser async

### Testing Approach ACTUAL
- **Local Testing**: `func start --verbose` con SAVE_LOCAL_COPIES=true
- **Performance Monitoring**: Log analysis después de cada change
- **File Inspection**: Verificar TIFF quality en local_output/
- **Memory Testing**: Monitor con documentos grandes

**Este proyecto está en producción activa. Seguir estas guías EXACTAMENTE para mantener reliability y performance.**