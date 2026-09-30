from typing import Optional
from pydantic import BaseModel, ConfigDict


class DriverProfileResponse(BaseModel):
    id: str
    fullName: str
    mobileNumber: str
    email: str
    dateOfBirth: Optional[str] = None
    address: Optional[str] = None
    emergencyContact: Optional[str] = None
    yearsOfExperience: int = 0
    isVerified: bool = False
    verificationStatus: str
    dutyStatus: str
    availability: str

    model_config = ConfigDict(from_attributes=True)


class DutyStatusUpdateSchema(BaseModel):
    status: str  # ONLINE, OFFLINE


class DutyStatusResponse(BaseModel):
    success: bool = True
    dutyStatus: str
    availabilityStatus: str
    message: str


class AvailabilityUpdateSchema(BaseModel):
    status: str  # UNAVAILABLE, AVAILABLE, BUSY


class AvailabilityResponse(BaseModel):
    success: bool = True
    availabilityStatus: str
    message: str
