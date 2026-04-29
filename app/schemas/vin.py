from pydantic import BaseModel
from typing import Optional, List


class VinDecodeResult(BaseModel):
    vin: str
    brand: str
    country: Optional[str] = None
    model: str
    year: Optional[int] = None
    engine: Optional[str] = None
    chassis: Optional[str] = None
    body_type: Optional[str] = None
    gvw: Optional[int] = None
    source: str = "mock"


class VinTreeNode(BaseModel):
    id: str
    name: str
    icon: Optional[str] = None
    keywords: Optional[List[str]] = None
    children: Optional[List["VinTreeNode"]] = []


class VinTreeResponse(BaseModel):
    vin: str
    vehicle: VinDecodeResult
    tree: List[VinTreeNode]


class VinSearchResult(BaseModel):
    section_id: str
    section_name: str
    keywords: List[str]
    products_count: int
    sample_products: List[dict]
