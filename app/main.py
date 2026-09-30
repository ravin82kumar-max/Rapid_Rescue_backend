import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database.database import engine
from app.api import (
    emergency_router,
    auth_router,
    driver_router,
    verification_router,
    admin_router,
    location_router,
    dispatch_router,
    websocket_router,
    ambulance_router,
    patient_router,
)

from contextlib import asynccontextmanager
from app.database.database import engine, AsyncSessionLocal
from app.services.admin_service import AdminService

# Ensure upload directories exist
os.makedirs("uploads/emergencies", exist_ok=True)
os.makedirs("uploads/driver_documents", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Seed default admin user if database is empty of admins
    async with AsyncSessionLocal() as session:
        try:
            await AdminService.create_default_admin_if_none(session)
        except Exception as e:
            print(f"Admin seeding notice: {e}")
    yield


app = FastAPI(
    title="RapidRescue API",
    description="Emergency Ambulance Backend - Patient, Driver & Admin Modules",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve uploaded files statically
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Register API routers
app.include_router(emergency_router)
app.include_router(auth_router)
app.include_router(driver_router)
app.include_router(verification_router)
app.include_router(admin_router)
app.include_router(location_router)
app.include_router(dispatch_router)
app.include_router(websocket_router)
app.include_router(ambulance_router)
app.include_router(patient_router)



@app.get("/")
async def root():
    return {
        "success": True,
        "message": "RapidRescue Backend is running 🚑"
    }


@app.get("/health/db")
async def database_health():
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))

    return {
        "success": True,
        "database": "PostgreSQL",
        "message": "Database connected successfully 🗄️"
    }