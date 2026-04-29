from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ReturnRequestCreate(BaseModel):
    order_id: str
    order_item_id: Optional[str] = None
    reason: str
    description: Optional[str] = None
    quantity: int = 1
    photos: Optional[List[str]] = None


class ReturnRequestResponse(BaseModel):
    id: str
    order_id: str
    order_item_id: Optional[str] = None
    order_number: str
    user_id: str
    user_email: str
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    status: str
    reason: str
    description: Optional[str]
    quantity: int
    refund_amount: float
    photos: Optional[List[str]]
    admin_notes: Optional[str]
    resolution: Optional[str]
    tracking_number: Optional[str]
    created_at: datetime
    inspected_at: Optional[datetime]
    refunded_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReturnRequestListResponse(BaseModel):
    requests: List[ReturnRequestResponse]
    total: int


class ReturnStatusUpdate(BaseModel):
    status: str
    admin_notes: Optional[str] = None
    resolution: Optional[str] = None
    refund_amount: Optional[float] = None


class ReturnTrackingUpdate(BaseModel):
    tracking_number: str
