from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AdminDashboardStats(BaseModel):
    total_users: int
    total_suppliers: int
    total_products: int
    total_orders: int
    total_revenue: float
    total_commission: float
    pending_disputes: int
    pending_verifications: int
    orders_today: int
    orders_change: float
    revenue_today: float
    revenue_change: float
    top_categories: List[dict]
    top_suppliers: List[dict]

class UserVerificationResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    user_type: str
    company_name: Optional[str] = None
    inn: Optional[str] = None
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

class DisputeCreate(BaseModel):
    order_id: str
    reason: str
    buyer_description: str

class DisputeResponse(BaseModel):
    id: str
    order_id: str
    order_number: str
    buyer_id: str
    buyer_email: str
    supplier_id: str
    supplier_name: str
    status: str
    reason: str
    buyer_description: str
    supplier_response: Optional[str] = None
    admin_resolution: Optional[str] = None
    refund_amount: float = 0.0
    assigned_to: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class CommissionRuleResponse(BaseModel):
    id: str
    name: str
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    commission_percent: float
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

class CommissionRuleCreate(BaseModel):
    name: str
    category_id: Optional[str] = None
    supplier_id: Optional[str] = None
    commission_percent: float
    is_active: bool = True

class CommissionRuleUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[str] = None
    supplier_id: Optional[str] = None
    commission_percent: Optional[float] = None
    is_active: Optional[bool] = None

class BannerResponse(BaseModel):
    id: str
    title: str
    subtitle: Optional[str] = None
    image_url: str
    link_url: Optional[str] = None
    position: str
    is_active: bool
    sort_order: int
    clicks_count: int = 0
    views_count: int = 0
    created_at: datetime
    class Config:
        from_attributes = True

class BannerCreate(BaseModel):
    title: str
    subtitle: Optional[str] = None
    image_url: str
    link_url: Optional[str] = None
    position: str = "home_top"
    is_active: bool = True
    sort_order: int = 0

class BannerUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    position: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
