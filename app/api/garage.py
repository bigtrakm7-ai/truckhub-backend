from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid

from app.core.database import get_db
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleUpdate, VehicleResponse, GarageResponse
from app.api.auth import get_current_active_user
from app.core.messages import Msg

router = APIRouter(prefix="/garage", tags=["Гараж"])


@router.get("/", response_model=GarageResponse)
async def get_garage(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Vehicle).where(Vehicle.user_id == current_user.id).order_by(Vehicle.is_default.desc(), Vehicle.created_at.desc())
    )
    vehicles = result.scalars().all()
    return GarageResponse(vehicles=vehicles, total=len(vehicles))


@router.post("/", response_model=VehicleResponse)
async def add_vehicle(
    vehicle_data: VehicleCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Vehicle).where(Vehicle.vin == vehicle_data.vin))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=Msg.VEHICLE_VIN_EXISTS)
    
    check_default = await db.execute(
        select(Vehicle).where(Vehicle.user_id == current_user.id, Vehicle.is_default == True)
    )
    has_default = check_default.scalar_one_or_none() is not None
    
    vehicle = Vehicle(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        vin=vehicle_data.vin,
        reg_number=vehicle_data.reg_number,
        vehicle_type=vehicle_data.vehicle_type,
        brand=vehicle_data.brand,
        model=vehicle_data.model,
        year=vehicle_data.year,
        engine=vehicle_data.engine,
        chassis=vehicle_data.chassis,
        mileage=vehicle_data.mileage,
        notes=vehicle_data.notes,
        is_default=not has_default,
    )
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: str,
    vehicle_data: VehicleUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.user_id == current_user.id)
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail=Msg.VEHICLE_NOT_FOUND)
    
    update_data = vehicle_data.dict(exclude_unset=True)
    
    if vehicle_data.is_default and not vehicle.is_default:
        result_reset = await db.execute(
            select(Vehicle).where(
                Vehicle.user_id == current_user.id,
                Vehicle.id != vehicle_id
            )
        )
        for v in result_reset.scalars().all():
            v.is_default = False
    
    for field, value in update_data.items():
        setattr(vehicle, field, value)
    
    await db.commit()
    await db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}")
async def delete_vehicle(
    vehicle_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.user_id == current_user.id)
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail=Msg.VEHICLE_NOT_FOUND)
    
    await db.delete(vehicle)
    await db.commit()
    return {"message": Msg.VEHICLE_DELETED}


@router.post("/{vehicle_id}/set-default")
async def set_default_vehicle(
    vehicle_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Vehicle).where(Vehicle.id == vehicle_id, Vehicle.user_id == current_user.id)
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail=Msg.VEHICLE_NOT_FOUND)
    
    result_all = await db.execute(
        select(Vehicle).where(Vehicle.user_id == current_user.id)
    )
    for v in result_all.scalars().all():
        v.is_default = v.id == vehicle_id
    
    await db.commit()
    return {"message": Msg.DEFAULT_VEHICLE_SET}
