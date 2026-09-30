from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict, Field


class AdminLoginSchema(BaseModel):
    identifier: str = Field(..., description="Admin email or mobile number")
    password: str = Field(..., description="Admin password")


class AdminLoginResponse(BaseModel):
    success: bool = True
    message: str = "Admin login successful"
    adminId: str
    fullName: str
    email: str
    role: str = "ADMIN"
    token: str
    isMockSession: bool = False
    createdAt: str


class AdminProfileSchema(BaseModel):
    adminId: str
    fullName: str
    email: str
    mobileNumber: Optional[str] = None
    role: str = "ADMIN"
    isActive: bool = True


class AdminDashboardSummarySchema(BaseModel):
    success: bool = True
    pendingReview: int
    underReview: int
    verifiedDrivers: int
    rejectedDrivers: int


class AdminDriverListItemSchema(BaseModel):
    driverId: str
    fullName: str
    mobileNumber: str
    email: str
    dateOfBirth: Optional[str] = None
    address: Optional[str] = None
    emergencyContact: Optional[str] = None
    yearsOfExperience: int = 0
    verificationStatus: str
    submittedAt: Optional[str] = None
    documentCount: int
    requiredDocumentCount: int = 6
    dutyStatus: str
    availabilityStatus: str
    ambulance: Optional[Any] = None


class AdminDocumentItemSchema(BaseModel):
    id: Optional[str] = None
    driverId: str
    documentType: str
    category: str
    originalFileName: str
    fileName: str
    mimeType: str
    fileSizeBytes: int
    size: int
    status: str
    uploadedAt: Optional[str] = None
    uri: str
    downloadUrl: str
    rejectionReason: Optional[str] = None


class AdminAmbulanceSchema(BaseModel):
    ambulanceId: str
    registrationNumber: str
    ambulanceType: str
    equipmentCapabilities: Optional[Any] = None
    hospitalAffiliation: Optional[str] = None


class AdminDriverDetailSchema(BaseModel):
    driverId: str
    fullName: str
    mobileNumber: str
    email: str
    dateOfBirth: Optional[str] = None
    dob: Optional[str] = None
    address: Optional[str] = None
    residentialAddress: Optional[str] = None
    emergencyContact: Optional[str] = None
    yearsOfExperience: int = 0
    verificationStatus: str
    submittedAt: Optional[str] = None
    dutyStatus: str
    availabilityStatus: str
    documentCount: int
    requiredDocumentCount: int = 6
    documents: List[AdminDocumentItemSchema]
    ambulance: Optional[AdminAmbulanceSchema] = None


class AdminRejectVerificationSchema(BaseModel):
    rejectedDocumentType: Optional[str] = None
    rejectionReason: str
