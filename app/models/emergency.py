import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database.database import Base


class EmergencyStatus(str, enum.Enum):
    SEARCHING = "SEARCHING"
    ACCEPTED = "ACCEPTED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Emergency(Base):
    __tablename__ = "emergencies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    patient_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )
    front_photo_path: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    rear_photo_path: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    latitude: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    longitude: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    accuracy: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50), default=EmergencyStatus.SEARCHING.value, nullable=False, index=True
    )
    assigned_ambulance_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )
    assigned_driver_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )

    # Extended driver/dispatch fields (optional/nullable to ensure backward compatibility)
    patient_name: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    patient_phone: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    pickup_address: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    emergency_type: Mapped[str | None] = mapped_column(String(100), nullable=True, default="MEDICAL_EMERGENCY")
    priority: Mapped[str | None] = mapped_column(String(50), nullable=True, default="CRITICAL")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    current_candidate_driver_id: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    dispatch_offered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    response_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

