from pydantic import BaseModel, validator, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class GLCodingEntry(BaseModel):
    """GL Coding entry for approval signature page"""
    accountCode: str = Field(..., min_length=1, max_length=20)
    accountDescription: str = Field(..., min_length=1, max_length=100)  # From accounts master table
    facilityCode: str = Field(..., min_length=1, max_length=10)
    facilityDescription: str = Field(..., min_length=1, max_length=100)  # From facilities master table
    taxCode: str = Field(..., min_length=1, max_length=10)
    amount: float = Field(..., gt=0)
    equipment: Optional[str] = Field(None, max_length=200)
    comments: Optional[str] = Field(None, max_length=200)


class DocumentProcessingRequest(BaseModel):
    """Simplified request - Function fetches complete data via TCRS API"""
    requestId: str = Field(..., pattern=r'^\d{12}$')  # 12-digit format
    approverName: str = Field(..., min_length=1, max_length=100)
    approverEmail: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    timestamp: datetime
    isRetry: bool = Field(default=False)  # Manual retry vs initial processing


class CompleteRequestData(BaseModel):
    """Complete data fetched from TCRS API"""
    requestId: str
    invoicePdfUrl: str
    requestInfo: Dict[str, Any]  # amount, vendor, company, branch
    glCodingData: List[GLCodingEntry]
    approverInfo: Dict[str, Any]  # name, email


class DocumentGenerationStatus(BaseModel):
    """Database status tracking"""
    requestId: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    consolidatedPdfUrl: Optional[str] = None
    tiffImageUrl: Optional[str] = None
    generatedAt: Optional[datetime] = None
    processingTimeMs: Optional[int] = None
    errorMessage: Optional[str] = None


class ProcessingResult(BaseModel):
    """Result of document processing operation"""
    success: bool
    requestId: str
    generatedFiles: Dict[str, str]  # consolidatedPdf, tiffImage URLs
    processedAt: str
    processingTimeMs: int
    isRetry: bool
    folder: str
    status: str