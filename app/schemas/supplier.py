from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class SupplierProductBase(BaseModel):
    article: str
    name: str
    price: float
    stock_quantity: int


class SupplierProductCreate(SupplierProductBase):
    description: Optional[str] = None
    is_active: bool = True


class SupplierProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    stock_quantity: Optional[int] = None
    is_active: Optional[bool] = None


class SupplierBulkProductsUpdate(BaseModel):
    product_ids: List[str]
    price: Optional[float] = None
    stock_quantity: Optional[int] = None
    is_active: Optional[bool] = None


class SupplierProductResponse(SupplierProductBase):
    id: str
    stock_status: str
    views_count: int = 0
    orders_count: int = 0
    conversion_rate: float = 0.0
    is_active: bool = True

    class Config:
        from_attributes = True


class PriceUploadResponse(BaseModel):
    id: str
    filename: str
    format: str
    import_kind: str = "products"
    total_products: int
    updated_products: int
    new_products: int
    errors: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class SupplierBalanceResponse(BaseModel):
    id: str
    amount: float
    transaction_type: str
    description: Optional[str]
    balance_before: float
    balance_after: float
    created_at: datetime

    class Config:
        from_attributes = True


class SupplierFinanceResponse(BaseModel):
    balance: float
    pending_amount: float
    available_amount: float
    total_earned: float
    total_commission: float
    transactions: List[SupplierBalanceResponse]


class SupplierAnalyticsResponse(BaseModel):
    total_views: int
    total_orders: int
    total_revenue: float
    conversion_rate: float
    top_products: List[SupplierProductResponse]
    views_by_day: List[dict]


class SupplierProductsListResponse(BaseModel):
    items: List[SupplierProductResponse]
    total: int
    page: int
    per_page: int
