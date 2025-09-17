# TCRS Document Processor

Azure Function for processing TCRS documents. Automatically generates consolidated PDFs with approval signatures and TIFF images from approved transportation cost requests.

## 🚀 Features

### Core Processing
- **PDF Consolidation**: Downloads invoice PDFs and merges with GL Coding approval pages
- **TIFF Generation**: Converts to optimized TIFF images (120 DPI, JPEG compression)
- **SAS URL Generation**: Secure blob access with 1-hour expiry tokens
- **Performance Monitoring**: Real-time timing analysis for each processing stage

### Integration
- **TCRS API Integration**: Fetches complete request data and updates status
- **Azure Blob Storage**: Secure document storage with automatic SAS authentication
- **Hybrid Processing**: HTTP trigger + manual retry capability via UI
- **Error Recovery**: Comprehensive error handling with retry mechanisms

## 🏗️ Architecture

- **Runtime**: Python 3.11 on Azure Functions
- **Trigger**: HTTP POST with manual retry support
- **Storage**: Azure Blob Storage with SAS authentication
- **API Integration**: TCRS internal endpoints for data and status

## 📋 API Reference

### `POST /api/process-documents`
**Request**:
```json
{
  "requestId": "202412150001",
  "approverName": "John Smith",
  "approverEmail": "john@company.com",
  "timestamp": "2024-12-15T10:30:00Z",
  "isRetry": false
}
```

**Response**:
```json
{
    "success": true,
    "requestId": "202412150001",
    "generatedFiles": {
      "consolidatedPdf":
  "https://storage.blob.core.windows.net/.../consolidated.pdf?sas_token",
      "tiffImage":
  "https://storage.blob.core.windows.net/.../document.tiff?sas_token"
    },
    "fileSizes": {
      "consolidatedPdfBytes": 2453120,
      "consolidatedPdfMB": 2.34,
      "tiffImageBytes": 8947200,
      "tiffImageMB": 8.53
    },
    "processedAt": "2024-12-15T10:32:15Z",
    "processingTimeMs": 11560,
    "isRetry": false,
    "folder": "company/branch/2024/12/",
    "status": "completed"
  }
```

### `GET /api/health`
Health check endpoint returning service status.

## ⚙️ Configuration

### Required Environment Variables
```bash
# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_ACCOUNT_NAME=your_storage_account
AZURE_STORAGE_ACCOUNT_KEY=your_storage_key
BLOB_CONTAINER_NAME=blob_container_name

# TCRS Integration
TCRS_API_BASE_URL=https://tcrscoded.azurewebsites.net
INTERNAL_FUNCTION_KEY=your_function_key

# Azure Functions
FUNCTIONS_WORKER_RUNTIME=python
AzureWebJobsStorage=your_functions_storage
```

### Optional Settings
```bash
LOG_LEVEL=INFO                    # DEBUG for verbose logging
TESTING_MODE=false                # Enable mock data
SAVE_LOCAL_COPIES=false          # Save files locally for debugging
SAS_EXPIRY_HOURS=1               # SAS token expiry (default: 1 hour)
ALLOWED_ORIGINS=https://...      # CORS configuration
```

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.11+
- Azure Functions Core Tools 4.x
- Azure Storage Account with blob container

### 2. Setup
```bash
# Clone and setup
git clone https://github.com/JuampaBiron/tcrs-document-processor.git
cd tcrs-document-processor

# Create virtual environment
python -m venv env311
.\env311\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp local.settings.example.json local.settings.json
# Edit local.settings.json with your Azure configuration
```

### 3. Run Locally
```bash
# Start Azure Functions runtime
func start --verbose

# Test endpoint
curl -X POST http://localhost:7071/api/process-documents \
  -H "Content-Type: application/json" \
  -d '{"requestId":"202412150001","approverName":"Test User","approverEmail":"test@company.com","timestamp":"2024-12-15T10:30:00Z","isRetry":false}'
```

## 📊 Performance Optimization

### TIFF Optimization
- **DPI**: 120 (balance of quality/size)
- **Compression**: JPEG 80% quality
- **Resizing**: Max 2000px width for memory efficiency
- **File Size**: ~70% reduction vs uncompressed

### Processing Pipeline
1. **Input Validation** (~0.01s)
2. **Fetch Request Data** (~0.4s)
3. **PDF Processing** (~1.8s): Download + Generate + Merge
4. **TIFF Conversion** (~0.6s): Optimized conversion
5. **Blob Upload** (~2.7s): With 5-minute timeout
6. **Status Update** (~0.5s)

**Total**: ~11.6s for typical request

## 🔧 Development

### Project Structure
```
src/
├── processors/
│   ├── pdf_processor.py      # PDF download, generation, merge
│   └── tiff_converter.py     # PDF to TIFF conversion
├── storage/
│   └── blob_client.py        # Azure Blob Storage with SAS
├── api/
│   └── tcrs_client.py        # TCRS API integration
├── models/
│   └── request_models.py     # Pydantic data models
└── utils/
    ├── logging_config.py     # Structured logging
    ├── performance.py        # Timing analysis
    └── validators.py         # Input validation
```

### Local Development
```bash
# Enable debug features
export SAVE_LOCAL_COPIES=true
export LOG_LEVEL=DEBUG

# Files saved to local_output/ for inspection
func start --verbose
```

## 🚀 Deployment

### Azure Function App
```bash
# Create Function App (Python 3.11)
az functionapp create --resource-group myResourceGroup \
  --consumption-plan-location eastus \
  --runtime python --runtime-version 3.11 \
  --functions-version 4 \
  --name tcrs-document-processor

# Deploy
func azure functionapp publish tcrs-document-processor
```

### Application Settings
Configure all required environment variables in Azure Portal > Function App > Configuration.

## 📈 Monitoring

- **Application Insights**: Automatic telemetry and performance tracking
- **Performance Metrics**: Detailed timing for each processing stage
- **Health Checks**: `/api/health` endpoint for uptime monitoring
- **Error Tracking**: Structured logging with request correlation IDs

## 🔒 Security

- **SAS Authentication**: Time-limited secure blob access
- **Function Key**: Protected API endpoints
- **Error Sanitization**: Safe error messages for API responses
- **CORS Configuration**: Restricted origins for security
- **File Size Reporting**: Monitor and detect unusually large files

---

**Built for TCRS at Finning International** | [Documentation](CLAUDE.md) | [Issues](https://github.com/JuampaBiron/tcrs-document-processor/issues)