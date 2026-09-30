import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class ResponseAction(str, enum.Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    TIMEOUT = "TIMEOUT"


class EmergencyResponse(Base):
    __tablename__ = "emergency_responses"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=lambda: f"RESP-{uuid.uuid4().hex[:12]}", index=True)
    request_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    driver_id: Mapped[str] = mapped_column(String(255), ForeignKey("drivers.id"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    response_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
