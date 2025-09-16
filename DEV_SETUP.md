# TCRS Document Processor - Development Setup

## Quick Start

1. **Run the setup script:**
   ```bash
   python setup.py
   ```

2. **Update local.settings.json with your Azure configuration**

3. **Start the function:**
   ```bash
   func start
   ```

4. **Test the function:**
   ```bash
   curl -X POST http://localhost:7071/api/process-documents \
     -H "Content-Type: application/json" \
     -d @test_request.json
   ```

## Manual Setup

### Prerequisites

- **Python 3.11+**: Required for Azure Functions and PDF processing
- **Azure Functions Core Tools 4.x**:
  ```bash
  npm install -g azure-functions-core-tools@4 --unsafe-perm true
  ```
- **Azure CLI** (optional, for deployment):
  ```bash
  # Windows
  winget install Microsoft.AzureCLI

  # macOS
  brew install azure-cli

  # Linux
  curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
  ```

### Environment Setup

1. **Create virtual environment:**
   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # macOS/Linux
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure local settings:**
   ```bash
   cp local.settings.example.json local.settings.json
   ```

   Update `local.settings.json` with your values:
   ```json
   {
     "Values": {
       "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=your_account;AccountKey=your_key;EndpointSuffix=core.windows.net",
       "BLOB_CONTAINER_NAME": "tcrs-documents",
       "TCRS_API_BASE_URL": "https://your-tcrs-app.azurewebsites.net",
       "INTERNAL_FUNCTION_KEY": "your_internal_function_key"
     }
   }
   ```

## Development Workflow

### Running Locally

```bash
# Start the Azure Functions runtime
func start

# Function will be available at:
# http://localhost:7071/api/process-documents
# http://localhost:7071/api/health
```

### Testing

```bash
# Run unit tests
python -m pytest tests/unit/ -v

# Run integration tests (requires Azure resources)
python -m pytest tests/integration/ -v

# Run all tests
python -m pytest -v

# Run with coverage
pip install pytest-cov
python -m pytest --cov=src tests/ -v
```

### Manual Testing

```bash
# Test successful processing
curl -X POST http://localhost:7071/api/process-documents \
  -H "Content-Type: application/json" \
  -d '{
    "requestId": "202412150001",
    "approverName": "John Smith",
    "approverEmail": "john@company.com",
    "timestamp": "2024-12-15T10:30:00Z",
    "isRetry": false
  }'

# Test health endpoint
curl http://localhost:7071/api/health
```

## Deployment

### Azure Resources Setup

```bash
# Login to Azure
az login

# Create Resource Group
az group create --name rg-tcrs-functions --location "East US"

# Create Storage Account
az storage account create \
  --name tcrsfunctionsstorage \
  --resource-group rg-tcrs-functions \
  --location "East US" \
  --sku Standard_LRS

# Create Function App
az functionapp create \
  --resource-group rg-tcrs-functions \
  --consumption-plan-location "East US" \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name tcrs-document-processor \
  --storage-account tcrsfunctionsstorage
```

### Deploy Function

```bash
# Deploy to Azure
func azure functionapp publish tcrs-document-processor --python

# Configure production settings
az functionapp config appsettings set \
  --name tcrs-document-processor \
  --resource-group rg-tcrs-functions \
  --settings @production.settings.json
```

## Troubleshooting

### Common Issues

1. **Python Version Error:**
   - Ensure Python 3.11+ is installed and activated in your virtual environment

2. **Azure Functions Core Tools Not Found:**
   ```bash
   npm install -g azure-functions-core-tools@4 --unsafe-perm true
   ```

3. **Missing Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables Not Set:**
   - Check `local.settings.json` exists and has correct values
   - Ensure no placeholder values like `"your_key"` remain

5. **PDF Processing Errors:**
   - Verify PyMuPDF and Pillow are installed correctly
   - Check that test PDF URLs are accessible

6. **Azure Connection Errors:**
   - Verify `AZURE_STORAGE_CONNECTION_STRING` is correct
   - Check that the storage account and container exist

### Debug Mode

Add to `local.settings.json`:
```json
{
  "Values": {
    "LOG_LEVEL": "DEBUG"
  }
}
```

### Log Analysis

```bash
# View function logs in real-time (when deployed)
func azure functionapp logstream tcrs-document-processor

# Query Application Insights
az monitor app-insights query \
  --app your-app-insights-name \
  --analytics-query "traces | where message contains 'TCRS'"
```

## Project Structure

```
tcrs-document-processor/
├── function_app.py              # Main Azure Function entry point
├── requirements.txt             # Python dependencies
├── host.json                   # Azure Functions configuration
├── local.settings.json         # Local environment variables
├── src/
│   ├── processors/
│   │   ├── pdf_processor.py    # PDF merge and signature logic
│   │   └── tiff_converter.py   # PDF to TIFF conversion
│   ├── storage/
│   │   └── blob_client.py      # Azure Blob Storage operations
│   ├── api/
│   │   └── tcrs_client.py      # TCRS API integration
│   ├── models/
│   │   └── request_models.py   # Pydantic data models
│   └── utils/
│       ├── validators.py       # Input validation
│       └── logging_config.py   # Structured logging
├── tests/
│   ├── unit/                   # Unit tests
│   └── integration/            # Integration tests
└── docs/                       # Additional documentation
```

## Key Features

- **Hybrid Processing**: HTTP trigger with manual retry support
- **Status Tracking**: Real-time status updates via TCRS API
- **Error Handling**: Comprehensive error handling with sanitized responses
- **Quality Assurance**: PDF validation and TIFF quality checks
- **Performance**: Async operations and optimized memory usage
- **Security**: Input validation and sanitized logging
- **Monitoring**: Structured logging and health checks