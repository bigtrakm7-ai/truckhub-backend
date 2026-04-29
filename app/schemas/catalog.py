from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CrossReference(BaseModel):
    original_article: str
    original_brand: str
    analog_article: str
    analog_brand: str
    compatibility: float


class BundleRecommendationItem(BaseModel):
    id: str
    article: str
    name: str
    brand: Optional[str]
    price: float
    reason: str
    score: float


class BundleRecommendationResponse(BaseModel):
    base_product_id: str
    recommendations: List[BundleRecommendationItem]


class SupplierOfferItem(BaseModel):
    id: str
    article: str
    supplier_name: Optional[str]
    brand_name: Optional[str]
    price: float
    stock_quantity: int
    stock_status_text: str


class CatalogOfferSummary(BaseModel):
    suppliers_count: int = 1
    offers_from_price: float


class ProductDetailResponse(BaseModel):
    id: str
    article: str
    name: str
    description: Optional[str]
    category_id: Optional[str]
    category_name: Optional[str]
    brand_id: Optional[str]
    brand_name: Optional[str]
    supplier_id: Optional[str]
    supplier_name: Optional[str]

    price: float
    old_price: Optional[float]

    stock_quantity: int
    stock_status: str
    stock_status_text: str
    delivery_days: Optional[int]

    weight: Optional[float]
    dimensions: Optional[str]

    images: List[str]
    applicability: List[str]

    cross_references: List[CrossReference] = []
    supplier_offers: List[SupplierOfferItem] = []

    is_premium: bool
    is_original: bool

    created_at: datetime

    class Config:
        from_attributes = True


class CatalogProductItem(ProductDetailResponse):
    offer_summary: Optional[CatalogOfferSummary] = None


class CategoryTreeResponse(BaseModel):
    id: str
    name: str
    slug: str
    image_url: Optional[str]
    product_count: int
    children: List["CategoryTreeResponse"] = []


class BrandListResponse(BaseModel):
    id: str
    name: str
    slug: str
    logo_url: Optional[str]
    country: Optional[str]
    product_count: int


class SearchSuggestion(BaseModel):
    article: str
    name: str
    brand: Optional[str]
    category: Optional[str]


class SearchResponse(BaseModel):
    products: List[CatalogProductItem]
    total: int
    page: int
    per_page: int
    total_pages: int
