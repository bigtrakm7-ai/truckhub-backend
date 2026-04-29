from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CategoryBase(BaseModel):
    name: str
    slug: Optional[str] = None
    parent_id: Optional[str] = None
    description: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: str
    image_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BrandBase(BaseModel):
    name: str
    slug: Optional[str] = None
    country: Optional[str] = None


class BrandCreate(BrandBase):
    pass


class BrandResponse(BrandBase):
    id: str
    logo_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    article: str
    name: str
    description: Optional[str] = None
    price: float
    old_price: Optional[float] = None
    stock_quantity: int = 0
    weight: Optional[float] = None
    dimensions: Optional[str] = None


class ProductCreate(ProductBase):
    category_id: Optional[str] = None
    brand_id: Optional[str] = None
    supplier_id: Optional[str] = None


class ProductResponse(ProductBase):
    id: str
    stock_status: str
    product_type: str
    is_premium: bool
    images: Optional[str] = None
    applicability: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProductSearchParams(BaseModel):
    query: Optional[str] = None
    category_id: Optional[str] = None
    brand_id: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    in_stock: Optional[bool] = None
    is_premium: Optional[bool] = None
    page: int = 1
    per_page: int = 20
