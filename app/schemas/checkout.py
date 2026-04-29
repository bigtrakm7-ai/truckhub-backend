from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CartItemBase(BaseModel):
    product_id: str
    quantity: int


class CartItemCreate(CartItemBase):
    pass


class CartItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    product_article: str
    supplier_id: str
    supplier_name: str
    quantity: int
    unit_price: float
    total_price: float
    stock_status: str
    delivery_days: int

    class Config:
        from_attributes = True


class CartResponse(BaseModel):
    id: str
    items: List[CartItemResponse]
    items_count: int
    subtotal: float
    delivery_price: float
    total_price: float
    suppliers: List[str]


class DeliveryEstimate(BaseModel):
    method: str
    name: str
    price: float
    days_min: int
    days_max: int
    logo: str


class CheckoutData(BaseModel):
    delivery_method: str
    delivery_address: Optional[str] = None
    pickup_point: Optional[str] = None
    comment: Optional[str] = None
    payment_method: str
    buyer_name: Optional[str] = None
    buyer_phone: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_phone: Optional[str] = None


class OrderCreateResponse(BaseModel):
    order_id: str
    order_number: str
    total_amount: float
    delivery_price: float
    status: str
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    payment_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DeliveryPoint(BaseModel):
    id: str
    name: str
    address: str
    city: str
    work_hours: str
