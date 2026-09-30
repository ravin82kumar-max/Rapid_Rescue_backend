from typing import Optional, Union
from pydantic import BaseModel, Field


class LocationUpdateSchema(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude (-90 to 90)")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude (-180 to 180)")
    accuracy: Optional[float] = Field(None, ge=0.0, description="Accuracy in meters")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    heading: Optional[float] = Field(None, ge=0.0, le=360.0, description="Heading in degrees (0-360)")
    speed: Optional[float] = Field(None, ge=0.0, description="Speed in m/s")
    timestamp: Optional[Union[int, float, str]] = Field(None, description="Timestamp in epoch ms or ISO string")


class LocationUpdateResponse(BaseModel):
    success: bool = True
    message: str = "Location updated successfully"
    recordedAt: str
