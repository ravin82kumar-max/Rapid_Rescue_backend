from typing import Optional
from pydantic import BaseModel, Field, field_validator


class DriverRegisterSchema(BaseModel):
    fullName: str = Field(..., min_length=2, description="Driver's full name")
    mobileNumber: str = Field(..., min_length=10, description="10-digit mobile number")
    email: str = Field(..., description="Driver's email address")
    dateOfBirth: Optional[str] = Field(None, description="YYYY-MM-DD")
    address: Optional[str] = Field(None, description="Residential address")
    emergencyContact: Optional[str] = Field(None, description="Emergency contact mobile number")
    password: str = Field(..., min_length=6, description="Password")
    confirmPassword: str = Field(..., description="Confirm password")
    driverIdPlaceholder: Optional[str] = Field(None, description="Optional custom driver ID / badge")
    yearsOfExperience: Optional[int] = Field(0, ge=0, description="Years of experience")

    @field_validator("confirmPassword")
    def passwords_match(cls, v, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


class DriverLoginSchema(BaseModel):
    mobileNumber: str = Field(..., min_length=10)
    password: str = Field(...)


class SessionData(BaseModel):
    userId: str
    role: str = "DRIVER"
    driverId: str
    name: str
    displayName: str
    mobileNumber: str
    email: str
    yearsOfExperience: int
    token: str
    createdAt: str
    isMockSession: bool = False


class LoginResponse(BaseModel):
    success: bool = True
    session: SessionData
    message: str = "Login successful"
