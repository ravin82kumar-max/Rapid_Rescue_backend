import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Text
from typing import List, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base

if TYPE_CHECKING:
    from app.models.admin_verification_action import AdminVerificationAction


class VerificationStatus(str, enum.Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    PENDING = "PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class DutyStatus(str, enum.Enum):
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"


class AvailabilityStatus(str, enum.Enum):
    UNAVAILABLE = "UNAVAILABLE"
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mobile_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[str | None] = mapped_column(String(50), nullable=True)
    residential_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(50), nullable=True)
    badge_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    years_of_experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(50), default=VerificationStatus.NOT_SUBMITTED.value, nullable=False, index=True
    )
    duty_status: Mapped[str] = mapped_column(
        String(50), default=DutyStatus.OFFLINE.value, nullable=False, index=True
    )
    availability_status: Mapped[str] = mapped_column(
        String(50), default=AvailabilityStatus.UNAVAILABLE.value, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )

    verification_actions: Mapped[List["AdminVerificationAction"]] = relationship(
        "AdminVerificationAction", back_populates="driver", cascade="all, delete-orphan"
    )

