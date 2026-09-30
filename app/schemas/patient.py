from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class PatientRegisterSchema(BaseModel):
    fullName: str = Field(..., min_length=2, description="Patient full name")
    mobileNumber: str = Field(..., min_length=5, max_length=20, description="Unique mobile number")
    password: str = Field(..., min_length=6, description="Account password")
    email: Optional[EmailStr] = Field(default=None, description="Optional email address")
    address: Optional[str] = Field(default=None, description="Optional residential address")
    bloodGroup: Optional[str] = Field(default=None, description="Optional blood group (e.g. A+, O-)")
    emergencyContactName: Optional[str] = Field(default=None, description="Optional emergency contact name")
    emergencyContactRelationship: Optional[str] = Field(default=None, description="Optional relationship")
    emergencyContactMobile: Optional[str] = Field(default=None, description="Optional emergency contact mobile")


class PatientLoginSchema(BaseModel):
    identifier: str = Field(..., description="Mobile number OR email address")
    password: str = Field(..., description="Account password")


class PatientSessionData(BaseModel):
    userId: str
    patientId: str
    role: str = "PATIENT"
    fullName: str
    mobileNumber: str
    email: Optional[str] = None
    token: str
    createdAt: str


class PatientLoginResponse(BaseModel):
    success: bool = True
    message: str = "Login successful"
    session: Optional[PatientSessionData] = None
    userId: Optional[str] = None
    patientId: Optional[str] = None
    role: Optional[str] = "PATIENT"
    fullName: Optional[str] = None
    mobileNumber: Optional[str] = None
    email: Optional[str] = None
    token: Optional[str] = None
    createdAt: Optional[str] = None


class PatientProfileSchema(BaseModel):
    id: str
    fullName: str
    mobileNumber: str
    email: Optional[str] = None
    address: Optional[str] = None
    bloodGroup: Optional[str] = None
    emergencyContactName: Optional[str] = None
    emergencyContactRelationship: Optional[str] = None
    emergencyContactMobile: Optional[str] = None
    createdAt: str

    class Config:
        from_attributes = True


class PatientUpdateSchema(BaseModel):
    fullName: Optional[str] = None
    mobileNumber: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    bloodGroup: Optional[str] = None
    emergencyContactName: Optional[str] = None
    emergencyContactRelationship: Optional[str] = None
    emergencyContactMobile: Optional[str] = None
