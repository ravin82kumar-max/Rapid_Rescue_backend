from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.models.driver import Driver
from app.utils.security import get_current_driver
from app.services.dispatch_service import DispatchService
from app.schemas.dispatch import (
    DispatchRespondSchema,
    DispatchRespondResponse,
    DispatchCompleteSchema,
    DispatchCompleteResponse,
)

router = APIRouter(prefix="/api/v1/dispatch", tags=["Dispatch"])


@router.post("/respond", response_model=DispatchRespondResponse)
async def respond_to_dispatch(
    data: DispatchRespondSchema,
    current_driver: Driver = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db),
):
    resp = await DispatchService.respond_to_dispatch(
        db=db,
        driver=current_driver,
        request_id_str=data.requestId,
        action_str=data.action,
    )

    return DispatchRespondResponse(
        success=True,
        requestId=resp.request_id,
        action=resp.action,
    )


@router.post("/complete", response_model=DispatchCompleteResponse)
async def complete_dispatch(
    data: DispatchCompleteSchema,
    current_driver: Driver = Depends(get_current_driver),
    db: AsyncSession = Depends(get_db),
):
    emergency = await DispatchService.complete_incident(
        db=db,
        driver=current_driver,
        request_id_str=data.requestId,
    )

    return DispatchCompleteResponse(
        success=True,
        requestId=str(emergency.id),
        status=emergency.status,
    )
