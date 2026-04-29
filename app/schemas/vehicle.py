from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.vehicle import VehicleType


class VehicleBase(BaseModel):
    vin: str
    reg_number: Optional[str] = None
    vehicle_type: VehicleType = VehicleType.TRUCK
    brand: str
    model: str
    year: Optional[int] = None
    engine: Optional[str] = None
    chassis: Optional[str] = None
    mileage: Optional[int] = None
    notes: Optional[str] = None


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    vin: Optional[str] = None
    reg_number: Optional[str] = None
    vehicle_type: Optional[VehicleType] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    engine: Optional[str] = None
    chassis: Optional[str] = None
    mileage: Optional[int] = None
    notes: Optional[str] = None
    is_default: Optional[bool] = None


class VehicleResponse(VehicleBase):
    id: str
    user_id: str
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True


class GarageResponse(BaseModel):
    vehicles: List[VehicleResponse]
    total: int
