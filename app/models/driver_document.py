import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class DocumentType(str, enum.Enum):
    DRIVING_LICENSE = "DRIVING_LICENSE"
    GOVERNMENT_ID = "GOVERNMENT_ID"
    DRIVER_SELFIE = "DRIVER_SELFIE"
    AMBULANCE_REGISTRATION = "AMBULANCE_REGISTRATION"
    AMBULANCE_PERMIT = "AMBULANCE_PERMIT"
    VEHICLE_INSURANCE = "VEHICLE_INSURANCE"


class DocumentCategory(str, enum.Enum):
    DRIVER = "DRIVER"
    AMBULANCE = "AMBULANCE"


class DocumentStatus(str, enum.Enum):
    NOT_UPLOADED = "NOT_UPLOADED"
    UPLOADED = "UPLOADED"
    REJECTED = "REJECTED"


class DriverDocument(Base):
    __tablename__ = "driver_documents"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: f"DOC-{uuid.uuid4().hex[:12]}", index=True)
    driver_id: Mapped[str] = mapped_column(String(255), ForeignKey("drivers.id"), index=True, nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=DocumentStatus.UPLOADED.value, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
