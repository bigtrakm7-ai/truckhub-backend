from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional

from app.core.database import get_db
from app.models.product import Product, Category, Brand
from app.models.supplier import Supplier
from app.schemas.product import ProductResponse, CategoryResponse, BrandResponse, ProductSearchParams
from app.core.messages import Msg

router = APIRouter(prefix="/products", tags=["Товары"])


@router.get("/", response_model=List[ProductResponse])
async def list_products(
    search: Optional[str] = Query(None, description="Поиск по артикулу или названию"),
    category_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock: Optional[bool] = None,
    is_premium: Optional[bool] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(Product).where(Product.is_active == True)
    
    if search:
        query = query.where(
            Product.article.ilike(f"%{search}%") | 
            Product.name.ilike(f"%{search}%")
        )
    if category_id:
        query = query.where(Product.category_id == category_id)
    if brand_id:
        query = query.where(Product.brand_id == brand_id)
    if min_price is not None:
        query = query.where(Product.price >= min_price)
    if max_price is not None:
        query = query.where(Product.price <= max_price)
    if in_stock:
        query = query.where(Product.stock_quantity > 0)
    if is_premium:
        query = query.where(Product.is_premium == True)
    
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    products = result.scalars().all()
    return products


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=Msg.PRODUCT_NOT_FOUND)
    return product


@router.get("/search/suggestions")
async def search_suggestions(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Product.article, Product.name)
        .where(
            Product.is_active == True,
            Product.article.ilike(f"%{q}%") | Product.name.ilike(f"%{q}%")
        )
        .limit(10)
    )
    suggestions = result.all()
    return {"suggestions": [{"article": s[0], "name": s[1]} for s in suggestions]}
