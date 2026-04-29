from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ServicePartnerBase(BaseModel):
    company_name: str
    inn: str
    address: str
    city: str
    phone: str
    email: Optional[str] = None
    services: Optional[str] = None
    working_hours: Optional[str] = None


class ServicePartnerCreate(ServicePartnerBase):
    pass


class ServicePartnerResponse(ServicePartnerBase):
    id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: float
    reviews_count: int
    is_verified: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ServiceSlotResponse(BaseModel):
    id: str
    partner_id: str
    date: str
    start_time: str
    end_time: str
    is_booked: bool

    class Config:
        from_attributes = True


class BookingCreate(BaseModel):
    partner_id: str
    slot_id: str
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    vehicle_vin: Optional[str] = None
    vehicle_model: Optional[str] = None
    service_type: str
    product_name: Optional[str] = None
    price: float
    notes: Optional[str] = None


class BookingResponse(BaseModel):
    id: str
    partner_id: str
    partner_name: str
    customer_name: str
    customer_phone: str
    vehicle_vin: Optional[str] = None
    vehicle_model: Optional[str] = None
    service_type: str
    product_name: Optional[str] = None
    appointment_date: datetime
    price: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class BookingListResponse(BaseModel):
    bookings: List[BookingResponse]
    total: int


class ReviewCreate(BaseModel):
    booking_id: str
    rating: int
    comment: Optional[str] = None
    photos: Optional[List[str]] = None


class ReviewResponse(BaseModel):
    id: str
    partner_id: str
    user_id: str
    rating: int
    comment: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
