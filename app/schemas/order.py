from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.core.enums import OrderStatus


class OrderItemBase(BaseModel):
    product_id: str
    quantity: int
    unit_price: float


class OrderItemCreate(OrderItemBase):
    is_installation: bool = False
    installation_date: Optional[datetime] = None
    service_center_id: Optional[str] = None


class OrderItemResponse(OrderItemBase):
    id: str
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    shipment_status: Optional[str] = None
    shipment_tracking_number: Optional[str] = None
    total_price: float
    is_installation: bool
    installation_date: Optional[datetime] = None
    service_center_id: Optional[str] = None

    class Config:
        from_attributes = True


class OrderBase(BaseModel):
    delivery_address: Optional[str] = None
    delivery_method: Optional[str] = None
    notes: Optional[str] = None


class OrderCreate(OrderBase):
    items: List[OrderItemCreate]


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    tracking_number: Optional[str] = None
    notes: Optional[str] = None


class OrderResponse(OrderBase):
    id: str
    order_number: str
    user_id: str
    status: OrderStatus
    total_amount: float
    delivery_amount: float
    commission_amount: float
    tracking_number: Optional[str] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    payment_url: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_phone: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_phone: Optional[str] = None
    created_at: datetime
    items: List[OrderItemResponse] = []
    shipments: List[dict] = []

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    id: str
    order_number: str
    status: OrderStatus
    total_amount: float
    delivery_address: Optional[str] = None
    delivery_method: Optional[str] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    buyer_name: Optional[str] = None
    recipient_name: Optional[str] = None
    created_at: datetime
    items_count: int
    shipments_count: int = 0

    class Config:
        from_attributes = True
