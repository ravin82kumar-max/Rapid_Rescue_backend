from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class DocumentResponseSchema(BaseModel):
    id: str
    driverId: str
    documentType: str
    category: str
    fileUrl: str
    fileName: str
    mimeType: str
    fileSizeBytes: int
    status: str
    rejectionReason: Optional[str] = None
    uploadedAt: datetime

    model_config = ConfigDict(from_attributes=True)


class VerificationStatusResponse(BaseModel):
    verificationStatus: str
    documents: List[DocumentResponseSchema]


class AdminRejectVerificationSchema(BaseModel):
    rejectedDocumentType: Optional[str] = None
    rejectionReason: str
