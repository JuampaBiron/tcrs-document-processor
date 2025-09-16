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
pydantic==2.5.0             # Data validation y models
```

### 3. Estructura de Archivos OBLIGATORIA
```
tcrs-document-processor/
├── function_app.py          # MAIN entry point - HTTP trigger function
├── requirements.txt         # EXACT versions listed above
├── host.json               # Azure Functions configuration
├── local.settings.json     # Local development settings (NOT committed)
├── src/
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── pdf_processor.py      # PDF merge logic
│   │   ├── tiff_converter.py     # PDF to TIFF conversion
│   │   └── signature_generator.py # Digital signature generation
│   ├── storage/
│   │   ├── __init__.py
│   │   └── blob_client.py        # Azure Blob Storage operations
│   ├── models/
│   │   ├── __init__.py
│   │   └── request_models.py     # Pydantic data models
│   └── utils/
│       ├── __init__.py
│       ├── validators.py         # Input validation functions
│       └── logging_config.py     # Structured logging setup
```

### 4. Function Entry Point Pattern
```python
# function_app.py (MANDATORY STRUCTURE)
import azure.functions as func
import logging
import json
from typing import Dict, Any
from src.processors.pdf_processor import PDFProcessor
from src.processors.tiff_converter import TIFFConverter
from src.storage.blob_client import BlobStorageClient
from src.models.request_models import DocumentProcessingRequest
from src.utils.logging_config import setup_logging

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
    
    try:
        # 1. Parse and validate input
        request_data = DocumentProcessingRequest.parse_raw(req.get_body())
        
        # 2. Update status to 'processing'
        await update_generation_status(request_data.requestId, 'processing')
        
        # 3. Fetch complete data from TCRS API
        complete_data = await fetch_complete_request_data(request_data.requestId)
        
        # 4. Process documents and update to 'completed'
        result = await process_documents_workflow(complete_data, request_data)
        
        return create_success_response(request_data, result)
        
    except Exception as e:
        # Update status to 'failed' for manual retry via UI
        if request_data:
            await update_generation_status(request_data.requestId, 'failed', str(e))
        
        return create_error_response(request_data, str(e))
```

### 5. Error Handling MANDATORIO
```python
# ALWAYS use this error handling pattern
try:
    # Business logic
    result = await process_request(validated_data)
    
    return func.HttpResponse(
        json.dumps({
            "success": True,
            "requestId": validated_data.requestId,
            "generatedFiles": result,
            "processedAt": datetime.utcnow().isoformat(),
            "processingTimeMs": processing_time
        }),
        status_code=200,
        mimetype="application/json"
    )
    
except ValidationError as e:
    logging.error(f"Validation error for request {request_id}: {str(e)}")
    return func.HttpResponse(
        json.dumps({
            "success": False,
            "error": "Invalid request format",
            "details": str(e),
            "requestId": request_id
        }),
        status_code=400,
        mimetype="application/json"
    )
    
except Exception as e:
    logging.error(f"Processing error for request {request_id}: {str(e)}", exc_info=True)
    return func.HttpResponse(
        json.dumps({
            "success": False,
            "error": "Internal processing error",
            "requestId": request_id,
            "timestamp": datetime.utcnow().isoformat()
        }),
        status_code=500,
        mimetype="application/json"
    )
```

### 6. Pydantic Models OBLIGATORIOS - Hybrid Approach
```python
# src/models/request_models.py
from pydantic import BaseModel, validator, Field
from typing import List, Optional
from datetime import datetime

class GLCodingEntry(BaseModel):
    accountCode: str = Field(..., min_length=1, max_length=20)
    accountDescription: str = Field(..., min_length=1, max_length=100)  # From accounts master table
    facilityCode: str = Field(..., min_length=1, max_length=10)
    facilityDescription: str = Field(..., min_length=1, max_length=100)  # From facilities master table
    taxCode: str = Field(..., min_length=1, max_length=10)
    amount: float = Field(..., gt=0)
    equipment: Optional[str] = Field(None, max_length=50)
    comments: Optional[str] = Field(None, max_length=200)

class DocumentProcessingRequest(BaseModel):
    """Simplified request - Function fetches complete data via TCRS API"""
    requestId: str = Field(..., regex=r'^\d{12}$')  # 12-digit format
    approverName: str = Field(..., min_length=1, max_length=100)
    approverEmail: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    timestamp: datetime
    isRetry: bool = Field(default=False)  # Manual retry vs initial processing

class CompleteRequestData(BaseModel):
    """Complete data fetched from TCRS API"""
    requestId: str
    invoicePdfUrl: str
    requestInfo: dict  # amount, vendor, company, branch
    glCodingData: List[GLCodingEntry]
    approverInfo: dict  # name, email

class DocumentGenerationStatus(BaseModel):
    """Database status tracking"""
    requestId: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    consolidatedPdfUrl: Optional[str] = None
    tiffImageUrl: Optional[str] = None
    generatedAt: Optional[datetime] = None
    processingTimeMs: Optional[int] = None
    errorMessage: Optional[str] = None
```

### 7. Azure Blob Storage Pattern
```python
# src/storage/blob_client.py
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import AzureError
import os
import logging

class BlobStorageClient:
    def __init__(self):
        self.connection_string = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
        self.container_name = os.environ["BLOB_CONTAINER_NAME"]
        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)

    async def upload_document(self, file_data: bytes, file_name: str, content_type: str) -> str:
        """Upload processed document to blob storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=file_name
            )
            
            await blob_client.upload_blob(
                data=file_data,
                content_settings=ContentSettings(content_type=content_type),
                overwrite=True
            )
            
            return blob_client.url
            
        except AzureError as e:
            logging.error(f"Blob upload failed for {file_name}: {str(e)}")
            raise
```

### 8. PDF Processing Requirements
```python
# src/processors/pdf_processor.py
import PyPDF2
import io
import aiohttp
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from datetime import datetime

class PDFProcessor:
    async def download_pdf(self, pdf_url: str) -> bytes:
        """Download PDF from Azure Blob Storage"""
        async with aiohttp.ClientSession() as session:
            async with session.get(pdf_url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download PDF: {response.status}")
                return await response.read()

    def generate_signature_page(self, request_data) -> bytes:
        """Generate signature page with approval info"""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        
        # Signature content
        c.drawString(100, 750, f"TCRS Approval Signature")
        c.drawString(100, 720, f"Request ID: {request_data.requestId}")
        c.drawString(100, 690, f"Approved by: {request_data.approverName}")
        c.drawString(100, 660, f"Date: {request_data.timestamp.strftime('%m/%d/%Y %H:%M:%S')}")
        c.drawString(100, 630, f"Approver Email: {request_data.approverEmail}")
        
        # GL Coding summary
        y_pos = 580
        c.drawString(100, y_pos, "GL Coding Summary:")
        for entry in request_data.glCodingData:
            y_pos -= 20
            c.drawString(120, y_pos, f"{entry.accountCode} - {entry.facilityCode}: ${entry.amount:,.2f}")
        
        c.save()
        buffer.seek(0)
        return buffer.getvalue()

    def merge_pdfs(self, invoice_pdf: bytes, signature_pdf: bytes) -> bytes:
        """Merge invoice PDF with signature page"""
        # Implementation using PyPDF2
```

### 9. Environment Variables REQUIRED
```json
// local.settings.json (NOT committed to git)
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=...",
    "BLOB_CONTAINER_NAME": "tcrs-documents",
    "ALLOWED_ORIGINS": "https://tcrscoded.azurewebsites.net,http://localhost:3000",
    "LOG_LEVEL": "INFO"
  }
}
```

### 10. Testing Requirements
```python
# tests/unit/test_pdf_processor.py
import pytest
from src.processors.pdf_processor import PDFProcessor
from src.models.request_models import DocumentProcessingRequest, GLCodingEntry

@pytest.fixture
def sample_request():
    return DocumentProcessingRequest(
        requestId="202412150001",
        approverName="John Smith",
        approverEmail="john@company.com",
        timestamp=datetime.now(),
        invoicePdfUrl="https://example.com/test.pdf",
        glCodingData=[
            GLCodingEntry(
                accountCode="1000",
                facilityCode="MAIN",
                taxCode="GST",
                amount=1500.00,
                equipment="CAT-950",
                comments="Test entry"
            )
        ]
    )

class TestPDFProcessor:
    def test_signature_generation(self, sample_request):
        processor = PDFProcessor()
        signature_pdf = processor.generate_signature_page(sample_request)
        assert len(signature_pdf) > 0
        assert isinstance(signature_pdf, bytes)
```

## 🚫 FORBIDDEN PRACTICES

### Architecture & Structure
- ❌ **NO Node.js** - Este proyecto es Python únicamente
- ❌ **NO multiple HTTP endpoints** - Un solo endpoint `/api/process-documents`
- ❌ **NO complex routing** - Azure Functions simple HTTP trigger
- ❌ **NO database connections** - Este es un stateless processor
- ❌ **NO local file storage** - Todo debe ir a Azure Blob Storage

### Dependencies & Libraries
- ❌ **NO outdated PDF libraries** - NO usar PyPDF2 < 3.0
- ❌ **NO img2pdf** - Usar Pillow para TIFF conversion
- ❌ **NO requests library** - Usar aiohttp para async operations
- ❌ **NO synchronous operations** - Todo debe ser async cuando sea posible

### Error Handling & Logging
- ❌ **NO silent failures** - Siempre log y return proper HTTP status
- ❌ **NO exposing internal errors** - Sanitize error messages for API responses
- ❌ **NO generic exception handling** - Catch específicos tipos de errores
- ❌ **NO console.log equivalents** - Usar Python logging module

### Security & Configuration
- ❌ **NO hardcoded URLs** - Usar environment variables
- ❌ **NO function keys in code** - Azure handle authentication
- ❌ **NO CORS wildcards** - Specific allowed origins only
- ❌ **NO sensitive data in logs** - Sanitize logging content

## 💡 DEVELOPMENT WORKFLOW - Hybrid Approach

### Setup New Feature
1. **FIRST**: Update models in `src/models/` para incluir status tracking
2. **SECOND**: Implement processor logic in `src/processors/`
3. **THIRD**: Add TCRS API client in `src/api/tcrs_client.py`
4. **FOURTH**: Update storage operations in `src/storage/`
5. **FIFTH**: Update main function in `function_app.py` con database status updates
6. **VERIFY**: Add unit tests en `tests/` incluyendo retry scenarios
7. **TEST**: Local testing con `func start` y manual retry flows

### Database Status Management
- **ALWAYS** update status to 'processing' before starting work
- **ALWAYS** update to 'completed' with file URLs on success  
- **ALWAYS** update to 'failed' with error message on exception
- **NEVER** leave status as 'processing' - always conclude with 'completed'/'failed'

### Code Quality Standards
- **Type Hints**: TODOS los functions deben tener type hints
- **Docstrings**: TODOS los public methods necesitan docstrings
- **Error Handling**: NUNCA bare `except:` statements
- **Async/Await**: Usar async operations para I/O
- **Logging**: Structured logging con context

### Performance Requirements
- **Memory Limit**: Function debe manejar PDFs hasta 50MB
- **Timeout**: Procesamiento completo < 5 minutos
- **Concurrency**: Support múltiple requests simultáneas
- **Resource Usage**: Optimizar memory usage para PDFs grandes

## 📋 INTEGRATION PATTERNS - Hybrid Approach

### 1. Automatic Processing (On Approval)
```typescript
// En approval API - automatic processing
export async function PUT(request: NextRequest) {
  // ... approval logic
  await updateRequestStatus(requestId, 'approved');
  
  // 1. Create database record FIRST
  await createDocumentGenerationRecord({
    requestId,
    status: 'pending',
    generatedBy: session.user.email
  });
  
  // 2. Trigger Azure Function (don't fail approval if this fails)
  try {
    await fetch(`${process.env.AZURE_FUNCTION_URL}/api/process-documents`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-functions-key': process.env.AZURE_FUNCTION_KEY
      },
      body: JSON.stringify({
        requestId,
        approverName: session.user.name,
        approverEmail: session.user.email,
        timestamp: new Date().toISOString(),
        isRetry: false
      })
    });
  } catch (error) {
    console.error('Document processing failed, but approval succeeded');
    // Status remains 'pending' for manual retry
  }
  
  return createSuccessResponse({ message: 'Request approved successfully' });
}
```

### 2. Manual Retry (UI Button)
```typescript
// Manual retry from UI component
const retryDocumentGeneration = async (requestId: string) => {
  try {
    // Update UI to show loading
    setRetrying(true);
    
    const response = await fetch(`${process.env.AZURE_FUNCTION_URL}/api/process-documents`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-functions-key': process.env.AZURE_FUNCTION_KEY
      },
      body: JSON.stringify({
        requestId,
        approverName: session.user.name,
        approverEmail: session.user.email,
        timestamp: new Date().toISOString(),
        isRetry: true  // Important: Mark as retry
      })
    });
    
    if (response.ok) {
      // Refresh status display
      await refreshDocumentStatus(requestId);
    } else {
      throw new Error('Retry failed');
    }
  } catch (error) {
    console.error('Manual retry failed:', error);
  } finally {
    setRetrying(false);
  }
};
```

### 3. Expected Response Format
```python
# ALWAYS return this structure
{
  "success": True,
  "requestId": "202412150001",
  "generatedFiles": {
    "consolidatedPdf": "https://storage.blob.core.windows.net/.../202412150001_consolidated_20241215_103215.pdf",
    "tiffImage": "https://storage.blob.core.windows.net/.../202412150001_document_20241215_103215.tiff"
  },
  "processedAt": "2024-12-15T10:32:15Z",
  "processingTimeMs": 2150,
  "isRetry": True,  # Indicates if this was a manual retry
  "folder": "company/branch/2024/12/",  # Same folder as original invoice
  "status": "completed"
}
```

### 4. TCRS API Integration
```python
# src/api/tcrs_client.py
class TCRSApiClient:
    def __init__(self):
        self.base_url = os.environ["TCRS_API_BASE_URL"]
        self.function_key = os.environ["INTERNAL_FUNCTION_KEY"]
    
    async def get_request_data(self, request_id: str) -> CompleteRequestData:
        """Fetch complete request data from TCRS internal API"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/api/internal/request-data/{request_id}",
                headers={"x-function-key": self.function_key}
            ) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch request data: {response.status}")
                data = await response.json()
                return CompleteRequestData(**data)
    
    async def update_generation_status(self, request_id: str, status: str, 
                                     file_urls: dict = None, 
                                     processing_time: int = None,
                                     error_message: str = None):
        """Update documentsGenerationTable via TCRS internal API"""
        payload = {
            "requestId": request_id,
            "status": status,
            "processingTimeMs": processing_time,
            "errorMessage": error_message
        }
        
        if file_urls:
            payload.update({
                "consolidatedPdfUrl": file_urls.get("consolidatedPdf"),
                "tiffImageUrl": file_urls.get("tiffImage")
            })
        
        async with aiohttp.ClientSession() as session:
            await session.put(
                f"{self.base_url}/api/internal/documents-generation/{request_id}",
                headers={
                    "Content-Type": "application/json",
                    "x-function-key": self.function_key
                },
                json=payload
            )
```

## 🎯 BUSINESS LOGIC REQUIREMENTS

### PDF Consolidation Requirements
1. **Merge Order**: Invoice PDF first, then signature page
2. **Signature Content**: Request ID, date/time, approver name, GL coding summary
3. **Quality**: Maintain original PDF quality y resolution
4. **Size Optimization**: Compress final PDF si > 10MB

### TIFF Conversion Requirements
1. **Resolution**: 300 DPI minimum para document quality
2. **Format**: Multi-page TIFF si el PDF tiene múltiples páginas
3. **Compression**: LZW compression para size optimization
4. **Color Mode**: RGB para preserve document formatting

### File Naming Convention
```python
# MANDATORY naming pattern
consolidated_pdf = f"{request_id}_consolidated_{timestamp}.pdf"
tiff_image = f"{request_id}_document_{timestamp}.tiff"

# timestamp format: YYYYMMDD_HHMMSS
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
```

**Este proyecto es crítico para el workflow de aprobaciones TCRS. Seguir estas guías exactamente para asegurar reliability y consistency.**