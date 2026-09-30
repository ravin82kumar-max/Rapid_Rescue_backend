from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.models.ambulance import AmbulanceType


class AmbulanceCreateSchema(BaseModel):
    registrationNumber: str = Field(..., min_length=2, description="Ambulance registration number (e.g. TN-37-AB-1234)")
    ambulanceType: str = Field(default="BLS", description="BLS | ALS | PATIENT_TRANSPORT")
    equipmentCapabilities: Optional[List[str]] = Field(default_factory=list, description="List of equipment capabilities e.g. ['OXYGEN', 'DEFIBRILLATOR']")
    hospitalAffiliation: Optional[str] = Field(None, description="Hospital affiliation")

    @field_validator("ambulanceType")
    def validate_type(cls, v: str) -> str:
        v_upper = v.upper()
        allowed = {t.value for t in AmbulanceType}
        if v_upper not in allowed:
            raise ValueError(f"Invalid ambulanceType '{v}'. Allowed types: {sorted(list(allowed))}")
        return v_upper


class AmbulanceResponseSchema(BaseModel):
    id: str
    driverId: Optional[str] = None
    registrationNumber: str
    ambulanceType: str
    equipmentCapabilities: Optional[Any] = None
    hospitalAffiliation: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
