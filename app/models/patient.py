import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    full_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    mobile_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    address: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    blood_group: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    emergency_contact_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    emergency_contact_relationship: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    emergency_contact_mobile: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
