import uuid
import enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database.database import Base


class VerificationActionEnum(str, enum.Enum):
    START_REVIEW = "START_REVIEW"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    RESUBMIT = "RESUBMIT"


class AdminVerificationAction(Base):
    __tablename__ = "admin_verification_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    driver_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("drivers.id"), nullable=False, index=True
    )
    admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    previous_status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    new_status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    rejected_document_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    admin: Mapped[Optional["AdminUser"]] = relationship(
        "AdminUser", back_populates="actions"
    )
    driver: Mapped["Driver"] = relationship(
        "Driver", back_populates="verification_actions"
    )
