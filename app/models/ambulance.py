import enum
import uuid
from sqlalchemy import String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class AmbulanceType(str, enum.Enum):
    BLS = "BLS"
    ALS = "ALS"
    PATIENT_TRANSPORT = "PATIENT_TRANSPORT"


class Ambulance(Base):
    __tablename__ = "ambulances"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: f"AMB-{uuid.uuid4().hex[:12]}", index=True)
    driver_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("drivers.id"), nullable=True, index=True)
    registration_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    ambulance_type: Mapped[str] = mapped_column(String(50), default=AmbulanceType.BLS.value, nullable=False)
    equipment_capabilities: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    hospital_affiliation: Mapped[str | None] = mapped_column(String(255), nullable=True)
