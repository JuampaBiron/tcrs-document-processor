# TCRS Document Processing - Azure Function

Azure Function para procesamiento automático de documentos PDF/TIFF cuando se aprueban requests en el sistema TCRS.

## 🎯 Propósito

Esta Azure Function recibe requests aprobadas via HTTP y genera:
1. **PDF consolidado**: Merge del Invoice PDF + GL Coding data
2. **Firma digital**: Timestamp con información del approver
3. **Imagen TIFF**: Conversión del PDF final a formato TIFF
4. **Storage en Azure Blob**: Almacenamiento de documentos generados

## 🏗️ Arquitectura

```
TCRS Next.js App ──HTTP POST──> Azure Function ──Process──> Azure Blob Storage
     │                              │                              │
     ├── Approval API               ├── PDF Generation              ├── Same folder as
     ├── Document Status API        ├── TIFF Conversion            │   original invoice
     └── Manual Retry Button        └── Database Status Update     └── Generated files
                                           │
                                           ▼
                                    documentsGenerationTable
                                    (pending → processing → completed/failed)
```

### **Hybrid Approach: HTTP + Manual Retry**
1. **Primary Path**: Immediate HTTP processing upon approval
2. **Fallback Path**: Manual retry by approver via UI if processing fails
3. **Status Tracking**: All operations tracked in database with real-time status
4. **User Control**: Approvers have full visibility and control over document generation

## 🚀 Stack Tecnológico

- **Runtime**: Python 3.11
- **Framework**: Azure Functions Core Tools 4.x
- **PDF Processing**: PyPDF2, ReportLab
- **Image Processing**: Pillow (PIL)
- **Storage**: Azure Blob Storage SDK
- **HTTP Client**: aiohttp para llamadas asíncronas

## 📁 Estructura del Proyecto

```
tcrs-document-processor/
├── function_app.py              # Entry point principal
├── requirements.txt             # Dependencias Python
├── host.json                   # Configuración Azure Functions
├── local.settings.json         # Variables locales (no commit)
├── .funcignore                 # Archivos a ignorar
├── src/
│   ├── processors/
│   │   ├── pdf_processor.py    # Lógica de PDF merge y firma
│   │   ├── tiff_converter.py   # Conversión PDF a TIFF
│   │   └── signature_generator.py # Generación de firmas
│   ├── storage/
│   │   └── blob_client.py      # Cliente Azure Blob Storage
│   ├── models/
│   │   └── request_models.py   # Modelos Pydantic
│   └── utils/
│       ├── validators.py       # Validación de inputs
│       └── logging_config.py   # Configuración de logging
├── tests/
│   ├── unit/
│   └── integration/
└── docs/
    ├── api.md                  # Documentación API
    └── deployment.md           # Guía de deployment
```

## 🔧 Desarrollo Local

### Prerequisitos
```bash
# Azure Functions Core Tools
npm install -g azure-functions-core-tools@4 --unsafe-perm true

# Python 3.11
python --version  # 3.11.x

# Azure CLI
az --version
```

### Setup Inicial
```bash
# Clonar y setup
git clone <repo-url>
cd tcrs-document-processor

# Virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables locales
cp local.settings.example.json local.settings.json
# Editar local.settings.json con tus valores
```

### Ejecutar Localmente
```bash
# Iniciar Azure Functions runtime
func start

# La función estará disponible en:
# http://localhost:7071/api/process-documents
```

## 🔐 Variables de Entorno

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=...",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;...",
    "BLOB_CONTAINER_NAME": "tcrs-documents",
    "ALLOWED_ORIGINS": "https://tcrscoded.azurewebsites.net,http://localhost:3000",
    "LOG_LEVEL": "INFO"
  }
}
```

## 📡 API Endpoints

### POST `/api/process-documents` (Primary Processing)

**Triggered by**: Approval action or manual retry button

**Request Body:**
```json
{
  "requestId": "202412150001",
  "approverName": "John Smith",
  "approverEmail": "john@company.com",
  "timestamp": "2024-12-15T10:30:00Z",
  "isRetry": false
}
```

**Note**: Function obtains complete data (invoice PDF, GL coding) via internal TCRS API call

**Response Success (200):**
```json
{
  "success": true,
  "requestId": "202412150001",
  "generatedFiles": {
    "consolidatedPdf": "https://storage.blob.core.windows.net/.../202412150001_consolidated.pdf",
    "tiffImage": "https://storage.blob.core.windows.net/.../202412150001_document.tiff"
  },
  "processedAt": "2024-12-15T10:32:15Z",
  "processingTimeMs": 2150,
  "isRetry": false,
  "folder": "company/branch/2024/12/"
}
```

**Response Error (400/500):**
```json
{
  "success": false,
  "error": "Invalid request format",
  "requestId": "202412150001",
  "timestamp": "2024-12-15T10:30:00Z"
}
```

## 🧪 Testing

```bash
# Unit tests
python -m pytest tests/unit/ -v

# Integration tests (requiere Azure Storage)
python -m pytest tests/integration/ -v

# Test manual con curl
curl -X POST http://localhost:7071/api/process-documents \
  -H "Content-Type: application/json" \
  -d @test-request.json
```

## 🚀 Deployment

### Azure Function App Setup
```bash
# Crear Resource Group
az group create --name rg-tcrs-functions --location "East US"

# Crear Storage Account
az storage account create \
  --name tcrsfunctionsstorage \
  --resource-group rg-tcrs-functions \
  --location "East US" \
  --sku Standard_LRS

# Crear Function App
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
# Build y deploy
func azure functionapp publish tcrs-document-processor --python

# Configurar variables de entorno
az functionapp config appsettings set \
  --name tcrs-document-processor \
  --resource-group rg-tcrs-functions \
  --settings @production.settings.json
```

## 📊 Monitoring

- **Application Insights**: Metrics y logging automático
- **Azure Monitor**: Alertas por errores y latencia
- **Blob Storage Logs**: Audit trail de documentos generados

### Logs Importantes
```bash
# Ver logs en tiempo real
func azure functionapp logstream tcrs-document-processor

# Query logs en Azure
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query "FunctionAppLogs | where FunctionName == 'process-documents'"
```

## 🔍 Troubleshooting

### Errores Comunes
1. **PDF Download Failed**: Verificar URL y permisos de blob storage
2. **TIFF Conversion Error**: Validar que PIL tenga todas las dependencias
3. **Memory Limit**: PDFs muy grandes pueden exceder límites de memoria
4. **Timeout**: Procesamiento >5 minutos requiere optimización

### Health Check
```bash
# Endpoint de salud
curl https://tcrs-document-processor.azurewebsites.net/api/health
```

## 🛡️ Seguridad

- **CORS**: Configurado solo para dominios autorizados
- **Authentication**: Function keys para acceso
- **Input Validation**: Validación estricta de todos los inputs
- **Blob Access**: SAS tokens con permisos mínimos
- **Error Handling**: No exposición de información sensible

## 📈 Performance

**Benchmarks esperados:**
- PDF simple (1-5 páginas): 1-3 segundos
- PDF complejo (10+ páginas): 3-8 segundos
- TIFF conversion: +2-5 segundos
- Upload a blob: +1-2 segundos

**Optimizaciones:**
- Procesamiento asíncrono
- Streaming de archivos grandes
- Caching de templates PDF
- Paralelización de operaciones

## 🔄 Integration con TCRS App

### **1. Approval Flow (Automatic Processing)**

En tu Next.js app, después de aprobar una request:

```typescript
// src/lib/document-processor.ts
export async function triggerDocumentProcessing(approvalData: {
  requestId: string;
  approverName: string;
  approverEmail: string;
  isRetry?: boolean;
}) {
  // 1. Create database record FIRST
  await createDocumentGenerationRecord({
    requestId: approvalData.requestId,
    status: 'pending',
    generatedBy: approvalData.approverEmail
  });

  // 2. Trigger Azure Function
  const response = await fetch(process.env.AZURE_FUNCTION_URL + '/api/process-documents', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-functions-key': process.env.AZURE_FUNCTION_KEY
    },
    body: JSON.stringify({
      requestId: approvalData.requestId,
      approverName: approvalData.approverName,
      approverEmail: approvalData.approverEmail,
      timestamp: new Date().toISOString(),
      isRetry: approvalData.isRetry || false
    })
  });

  // 3. Don't fail approval if document processing fails
  if (!response.ok) {
    console.error(`Document processing failed: ${response.statusText}`);
    // Status remains 'pending' for manual retry
    return { success: false, error: response.statusText };
  }

  return await response.json();
}
```

### **2. Manual Retry Flow (UI Button)**

```typescript
// src/hooks/use-document-status.ts
export function useDocumentStatus(requestId: string) {
  const [status, setStatus] = useState<DocumentStatus | null>(null);
  const [loading, setLoading] = useState(false);

  const retryGeneration = async () => {
    setLoading(true);
    try {
      const result = await triggerDocumentProcessing({
        requestId,
        approverName: session.user.name,
        approverEmail: session.user.email,
        isRetry: true
      });
      
      if (result.success) {
        setStatus('completed');
      }
    } catch (error) {
      console.error('Retry failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return { status, loading, retryGeneration };
}
```

### **3. Status Display Component**

```typescript
// src/components/request/document-generation-status.tsx
export function DocumentGenerationStatus({ requestId }: { requestId: string }) {
  const { status, loading, retryGeneration } = useDocumentStatus(requestId);

  return (
    <div className="border rounded-lg p-4">
      <h4 className="font-semibold mb-2">📄 Document Generation Status</h4>
      
      <div className="flex items-center gap-2 mb-3">
        {status === 'pending' && <span className="text-yellow-600">⏳ Pending</span>}
        {status === 'processing' && <span className="text-blue-600">🔄 Processing...</span>}
        {status === 'completed' && <span className="text-green-600">✅ Completed</span>}
        {status === 'failed' && <span className="text-red-600">❌ Failed</span>}
      </div>

      {status === 'completed' && (
        <div className="space-y-2">
          <a href={`/api/documents/${requestId}/consolidated.pdf`} target="_blank">
            📑 Consolidated PDF [View] [Download]
          </a>
          <a href={`/api/documents/${requestId}/document.tiff`} target="_blank">
            🖼️ TIFF Document [View] [Download]
          </a>
        </div>
      )}

      {(status === 'failed' || status === 'pending') && (
        <button
          onClick={retryGeneration}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Regenerating...' : 'Regenerate Documents'}
        </button>
      )}
    </div>
  );
}
```