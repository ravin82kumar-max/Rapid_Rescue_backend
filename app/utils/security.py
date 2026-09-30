from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.database import settings, get_db

security_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode("utf-8")
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    hash_bytes = hashed_password.encode("utf-8")
    try:
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_driver(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
):
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing or invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    driver_id = payload.get("driver_id") or payload.get("sub")
    if not driver_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing driver identity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from app.models.driver import Driver
    stmt = select(Driver).where(Driver.id == str(driver_id))
    result = await db.execute(stmt)
    driver = result.scalar_one_or_none()

    if not driver:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Driver account not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return driver


async def get_current_patient(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
):
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing or invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    role = payload.get("role")
    if role and role != "PATIENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Patient access required.",
        )

    patient_id = payload.get("patient_id") or payload.get("sub")
    if not patient_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing patient identity.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    import uuid
    from app.models.patient import Patient

    try:
        patient_uuid = uuid.UUID(str(patient_id))
    except ValueError:
        patient_uuid = None

    if patient_uuid:
        stmt = select(Patient).where(Patient.id == patient_uuid)
    else:
        stmt = select(Patient).where(Patient.id == str(patient_id))

    result = await db.execute(stmt)
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Patient account not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return patient


async def get_optional_patient(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
):
    if not credentials or not credentials.credentials:
        return None

    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        patient_id = payload.get("patient_id") or payload.get("sub")
        if not patient_id:
            return None

        import uuid
        from app.models.patient import Patient

        try:
            patient_uuid = uuid.UUID(str(patient_id))
        except ValueError:
            patient_uuid = None

        if patient_uuid:
            stmt = select(Patient).where(Patient.id == patient_uuid)
        else:
            stmt = select(Patient).where(Patient.id == str(patient_id))

        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception:
        return None

