from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional
import math
from difflib import SequenceMatcher

from app.core.database import get_db
from app.models.product import Product, Category, Brand
from app.models.supplier import Supplier
from app.schemas.catalog import (
    ProductDetailResponse,
    CatalogProductItem,
    CatalogOfferSummary,
    CategoryTreeResponse,
    BrandListResponse,
    SearchSuggestion,
    SearchResponse,
    CrossReference,
    BundleRecommendationResponse,
    BundleRecommendationItem,
    SupplierOfferItem,
)
from app.schemas.vin import VinDecodeResult, VinTreeResponse, VinTreeNode, VinSearchResult
from app.services.integration_service import integration_service
from app.services.performance import cache_response, SearchOptimizer
from app.core.messages import Msg

router = APIRouter(prefix="/catalog", tags=["Каталог"])


def _catalog_group_key(product: Product) -> str:
    article = _normalize_article(product.article)
    if article:
        return article
    return (product.name or "").strip().lower()


def _fuzzy_match_score(query: str, article: str, name: str) -> float:
    q = (query or "").strip().lower()
    if not q:
        return 0.0
    a = (article or "").lower()
    n = (name or "").lower()

    if q in a:
        return 1.0
    if q in n:
        return 0.95

    a_ratio = SequenceMatcher(None, q, a).ratio() if a else 0.0
    n_ratio = SequenceMatcher(None, q, n).ratio() if n else 0.0

    n_tokens = [t for t in n.replace("-", " ").replace("_", " ").split() if t]
    token_ratio = max((SequenceMatcher(None, q, t).ratio() for t in n_tokens), default=0.0)

    return max(a_ratio, n_ratio, token_ratio)


def _normalize_article(value: str) -> str:
    src = (value or "").upper()
    chars = [ch for ch in src if ch.isalnum()]
    return "".join(chars)


def _compatibility_score(base: Product, candidate: Product) -> float:
    score = 0.0

    base_article = _normalize_article(base.article)
    cand_article = _normalize_article(candidate.article)
    if base_article and cand_article:
        if base_article == cand_article:
            score += 0.7
        else:
            ratio = SequenceMatcher(None, base_article, cand_article).ratio()
            score += 0.35 * ratio

    base_name = (base.name or "").lower()
    cand_name = (candidate.name or "").lower()
    if base_name and cand_name:
        score += 0.2 * SequenceMatcher(None, base_name, cand_name).ratio()

    if base.brand_id and candidate.brand_id and base.brand_id == candidate.brand_id:
        score += 0.1

    if base.category_id and candidate.category_id and base.category_id == candidate.category_id:
        score += 0.1

    if base.product_type != candidate.product_type:
        score += 0.05

    return round(min(score, 0.99), 2)


def _name_similarity(base: Product, candidate: Product) -> float:
    base_name = (base.name or "").lower()
    cand_name = (candidate.name or "").lower()
    if not base_name or not cand_name:
        return 0.0
    return SequenceMatcher(None, base_name, cand_name).ratio()


def _bundle_recommendation_score(base: Product, candidate: Product) -> tuple[float, str]:
    score = 0.0
    reason = "Сопутствующий товар"

    if getattr(base, "brand_id", None) and getattr(base, "brand_id", None) == getattr(candidate, "brand_id", None):
        score += 0.2
        reason = "Тот же бренд"

    if getattr(base, "supplier_id", None) and getattr(base, "supplier_id", None) == getattr(candidate, "supplier_id", None):
        score += 0.1
        reason = "Тот же поставщик"

    if getattr(base, "category_id", None) and getattr(base, "category_id", None) == getattr(candidate, "category_id", None):
        score += 0.1

    base_price = float(getattr(base, "price", 0) or 0)
    cand_price = float(getattr(candidate, "price", 0) or 0)
    if base_price > 0 and cand_price > 0 and cand_price <= base_price * 0.6:
        score += 0.2
        reason = "Часто покупают в комплекте"

    if int(getattr(candidate, "stock_quantity", 0) or 0) > 0:
        score += 0.15

    if bool(getattr(candidate, "is_premium", False)):
        score += 0.05

    base_app = set((getattr(base, "applicability", "") or "").lower().split())
    cand_app = set((getattr(candidate, "applicability", "") or "").lower().split())
    if base_app and cand_app and base_app.intersection(cand_app):
        score += 0.2
        reason = "Подходит к той же технике"

    base_tokens = set((getattr(base, "name", "") or "").lower().replace("-", " ").split())
    cand_tokens = set((getattr(candidate, "name", "") or "").lower().replace("-", " ").split())
    common = base_tokens.intersection(cand_tokens)
    if common:
        score += 0.1

    return round(min(score, 0.99), 2), reason


@router.get("/categories", response_model=List[CategoryTreeResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Category).where(Category.parent_id == None)
    )
    categories = result.scalars().all()

    async def build_tree(category: Category) -> CategoryTreeResponse:
        count_result = await db.execute(
            select(func.count(Product.id)).where(Product.category_id == category.id)
        )
        product_count = count_result.scalar() or 0

        children_result = await db.execute(
            select(Category).where(Category.parent_id == category.id)
        )
        children = children_result.scalars().all()

        return CategoryTreeResponse(
            id=category.id,
            name=category.name,
            slug=category.slug,
            image_url=category.image_url,
            product_count=product_count,
            children=[await build_tree(c) for c in children]
        )

    return [await build_tree(c) for c in categories]


@router.get("/brands", response_model=List[BrandListResponse])
async def get_brands(
    category_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Brand)

    if category_id:
        query = query.join(Product).where(Product.category_id == category_id)

    query = query.distinct()
    result = await db.execute(query)
    brands = result.scalars().all()

    brand_responses = []
    for brand in brands:
        count_result = await db.execute(
            select(func.count(Product.id)).where(Product.brand_id == brand.id)
        )
        product_count = count_result.scalar() or 0

        brand_responses.append(BrandListResponse(
            id=brand.id,
            name=brand.name,
            slug=brand.slug,
            logo_url=brand.logo_url,
            country=brand.country,
            product_count=product_count
        ))

    return brand_responses


@router.get("/search/suggestions")
async def search_suggestions(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Product.article, Product.name, Brand.name, Category.name)
        .outerjoin(Brand, Product.brand_id == Brand.id)
        .outerjoin(Category, Product.category_id == Category.id)
        .where(
            or_(
                Product.article.ilike(f"%{q}%"),
                Product.name.ilike(f"%{q}%")
            ),
            Product.is_active == True
        )
        .limit(10)
    )
    suggestions = result.all()
    return {
        "suggestions": [
            SearchSuggestion(
                article=s[0],
                name=s[1],
                brand=s[2],
                category=s[3]
            )
            for s in suggestions
        ]
    }


@router.get("/search", response_model=SearchResponse)
@cache_response(ttl_seconds=30, key_prefix="catalog:search")
async def search_products(
    q: Optional[str] = None,
    category_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock: Optional[bool] = None,
    is_premium: Optional[bool] = None,
    sort_by: Optional[str] = "relevance",
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(Product).where(Product.is_active == True)

    if q:
        query = query.where(
            or_(
                Product.article.ilike(f"%{q}%"),
                Product.name.ilike(f"%{q}%")
            )
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

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    if sort_by == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort_by == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort_by == "name":
        query = query.order_by(Product.name.asc())
    else:
        if is_premium:
            query = query.order_by(Product.is_premium.desc())
        query = query.order_by(Product.created_at.desc())

    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    products = result.scalars().all()

    if q and not products:
        fuzzy_query = select(Product).where(Product.is_active == True).limit(300)
        fuzzy_result = await db.execute(fuzzy_query)
        fuzzy_products = fuzzy_result.scalars().all()

        scored = [(p, _fuzzy_match_score(q, p.article, p.name)) for p in fuzzy_products]
        scored = [item for item in scored if item[1] >= 0.55]
        scored.sort(key=lambda item: item[1], reverse=True)

        total = len(scored)
        start = (page - 1) * per_page
        end = start + per_page
        products = [item[0] for item in scored[start:end]]

    grouped: dict[str, list[Product]] = {}
    for product in products:
        key = _catalog_group_key(product)
        grouped.setdefault(key, []).append(product)

    grouped_products = list(grouped.values())

    product_responses = []
    for group in grouped_products:
        group_sorted = sorted(group, key=lambda item: (item.price, -(item.stock_quantity or 0)))
        product = group_sorted[0]
        brand_name = None
        if product.brand_id:
            brand_result = await db.execute(select(Brand).where(Brand.id == product.brand_id))
            brand = brand_result.scalar_one_or_none()
            if brand:
                brand_name = brand.name

        category_name = None
        if product.category_id:
            cat_result = await db.execute(select(Category).where(Category.id == product.category_id))
            cat = cat_result.scalar_one_or_none()
            if cat:
                category_name = cat.name

        supplier_name = None
        if product.supplier_id:
            sup_result = await db.execute(select(Supplier).where(Supplier.id == product.supplier_id))
            sup = sup_result.scalar_one_or_none()
            if sup:
                supplier_name = sup.company_name

        stock_text = "Нет в наличии"
        if product.stock_status.value == "in_stock":
            stock_text = f"В наличии ({product.stock_quantity} шт.)"
        elif product.stock_status.value == "on_order":
            stock_text = "Под заказ"

        images = []
        if product.images:
            images = product.images.split(",")

        applicability = []
        if product.applicability:
            applicability = product.applicability.split("\n")

        suppliers = {item.supplier_id or item.id for item in group}
        lowest_price = min(item.price for item in group)

        product_responses.append(CatalogProductItem(
            id=product.id,
            article=product.article,
            name=product.name,
            description=product.description,
            category_id=product.category_id,
            category_name=category_name,
            brand_id=product.brand_id,
            brand_name=brand_name,
            supplier_id=product.supplier_id,
            supplier_name=supplier_name,
            price=product.price,
            old_price=product.old_price,
            stock_quantity=product.stock_quantity,
            stock_status=product.stock_status.value,
            stock_status_text=stock_text,
            delivery_days=3 if product.stock_quantity > 0 else 14,
            weight=product.weight,
            dimensions=product.dimensions,
            images=images,
            applicability=applicability,
            is_premium=product.is_premium,
            is_original=product.product_type.value == "original",
            created_at=product.created_at,
            cross_references=[],
            offer_summary=CatalogOfferSummary(
                suppliers_count=len(suppliers),
                offers_from_price=lowest_price,
            ),
        ))

    return SearchResponse(
        products=product_responses,
        total=len(grouped_products) if grouped_products else total,
        page=page,
        per_page=per_page,
        total_pages=0 if len(grouped_products) == 0 else math.ceil(len(grouped_products) / per_page)
    )


@router.get("/product/{product_id}", response_model=ProductDetailResponse)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=Msg.PRODUCT_NOT_FOUND)

    brand_name = None
    if product.brand_id:
        brand_result = await db.execute(select(Brand).where(Brand.id == product.brand_id))
        brand = brand_result.scalar_one_or_none()
        if brand:
            brand_name = brand.name

    category_name = None
    if product.category_id:
        cat_result = await db.execute(select(Category).where(Category.id == product.category_id))
        cat = cat_result.scalar_one_or_none()
        if cat:
            category_name = cat.name

    supplier_name = None
    if product.supplier_id:
        sup_result = await db.execute(select(Supplier).where(Supplier.id == product.supplier_id))
        sup = sup_result.scalar_one_or_none()
        if sup:
            supplier_name = sup.company_name

    stock_text = "Нет в наличии"
    if product.stock_status.value == "in_stock":
        stock_text = f"В наличии ({product.stock_quantity} шт.)"
    elif product.stock_status.value == "on_order":
        stock_text = "Под заказ"

    images = []
    if product.images:
        images = product.images.split(",")

    applicability = []
    if product.applicability:
        applicability = product.applicability.split("\n")

    cross_refs = []
    if product.article:
        analogs_result = await db.execute(
            select(Product)
            .where(
                Product.id != product.id,
                Product.is_active == True
            )
            .limit(120)
        )
        analogs = analogs_result.scalars().all()

        scored_analogs = []
        for analog in analogs:
            comp = _compatibility_score(product, analog)
            if comp >= 0.45:
                scored_analogs.append((analog, comp))

        scored_analogs.sort(key=lambda item: item[1], reverse=True)

        for analog, comp in scored_analogs[:10]:
            analog_brand_name = "Unknown"
            if analog.brand_id:
                analog_brand_result = await db.execute(select(Brand).where(Brand.id == analog.brand_id))
                analog_brand = analog_brand_result.scalar_one_or_none()
                if analog_brand:
                    analog_brand_name = analog_brand.name

            cross_refs.append(CrossReference(
                original_article=product.article,
                original_brand=brand_name or "Unknown",
                analog_article=analog.article,
                analog_brand=analog_brand_name,
                compatibility=comp
            ))

    offers: List[SupplierOfferItem] = []
    offers_result = await db.execute(
        select(Product)
        .where(
            Product.id != product.id,
            Product.is_active == True,
        )
        .limit(300)
    )
    offer_candidates = offers_result.scalars().all()

    scored_offers: list[tuple[Product, float]] = []
    for candidate in offer_candidates:
        score = 0.0
        if product.brand_id and candidate.brand_id and product.brand_id == candidate.brand_id:
            score += 0.35
        if product.category_id and candidate.category_id and product.category_id == candidate.category_id:
            score += 0.25
        if _normalize_article(product.article) == _normalize_article(candidate.article):
            score += 0.6
        else:
            score += 0.3 * _name_similarity(product, candidate)
        if candidate.stock_quantity > 0:
            score += 0.1
        if score >= 0.45:
            scored_offers.append((candidate, score))

    scored_offers.sort(key=lambda item: (item[1], item[0].stock_quantity, -item[0].price), reverse=True)

    for candidate, _score in scored_offers[:6]:
        candidate_brand_name = None
        if candidate.brand_id:
            candidate_brand_result = await db.execute(select(Brand).where(Brand.id == candidate.brand_id))
            candidate_brand = candidate_brand_result.scalar_one_or_none()
            if candidate_brand:
                candidate_brand_name = candidate_brand.name

        candidate_supplier_name = None
        if candidate.supplier_id:
            candidate_supplier_result = await db.execute(select(Supplier).where(Supplier.id == candidate.supplier_id))
            candidate_supplier = candidate_supplier_result.scalar_one_or_none()
            if candidate_supplier:
                candidate_supplier_name = candidate_supplier.company_name

        candidate_stock_text = "Нет в наличии"
        if candidate.stock_status.value == "in_stock":
            candidate_stock_text = f"В наличии ({candidate.stock_quantity} шт.)"
        elif candidate.stock_status.value == "on_order":
            candidate_stock_text = "Под заказ"

        offers.append(
            SupplierOfferItem(
                id=candidate.id,
                article=candidate.article,
                supplier_name=candidate_supplier_name,
                brand_name=candidate_brand_name,
                price=candidate.price,
                stock_quantity=candidate.stock_quantity,
                stock_status_text=candidate_stock_text,
            )
        )

    return ProductDetailResponse(
        id=product.id,
        article=product.article,
        name=product.name,
        description=product.description,
        category_id=product.category_id,
        category_name=category_name,
        brand_id=product.brand_id,
        brand_name=brand_name,
        supplier_id=product.supplier_id,
        supplier_name=supplier_name,
        price=product.price,
        old_price=product.old_price,
        stock_quantity=product.stock_quantity,
        stock_status=product.stock_status.value,
        stock_status_text=stock_text,
        delivery_days=3 if product.stock_quantity > 0 else 14,
        weight=product.weight,
        dimensions=product.dimensions,
        images=images,
        applicability=applicability,
        cross_references=cross_refs,
        supplier_offers=offers,
        is_premium=product.is_premium,
        is_original=product.product_type.value == "original",
        created_at=product.created_at
    )


@router.get("/product/{product_id}/bundles", response_model=BundleRecommendationResponse)
async def get_bundle_recommendations(
    product_id: str,
    limit: int = Query(8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    base = result.scalar_one_or_none()
    if not base:
        raise HTTPException(status_code=404, detail=Msg.PRODUCT_NOT_FOUND)

    candidates_result = await db.execute(
        select(Product)
        .where(Product.id != base.id, Product.is_active == True)
        .limit(300)
    )
    candidates = candidates_result.scalars().all()

    scored: list[tuple[Product, float, str]] = []
    for candidate in candidates:
        score, reason = _bundle_recommendation_score(base, candidate)
        if score >= 0.35:
            scored.append((candidate, score, reason))

    scored.sort(key=lambda item: item[1], reverse=True)

    recommendations: List[BundleRecommendationItem] = []
    for candidate, score, reason in scored[:limit]:
        brand_name = None
        if candidate.brand_id:
            brand_result = await db.execute(select(Brand).where(Brand.id == candidate.brand_id))
            brand = brand_result.scalar_one_or_none()
            if brand:
                brand_name = brand.name

        recommendations.append(
            BundleRecommendationItem(
                id=candidate.id,
                article=candidate.article,
                name=candidate.name,
                brand=brand_name,
                price=candidate.price,
                reason=reason,
                score=score,
            )
        )

    return BundleRecommendationResponse(
        base_product_id=base.id,
        recommendations=recommendations,
    )


@router.get("/vin/{vin}", response_model=VinDecodeResult)
async def get_vehicle_by_vin(
    vin: str = Path(..., min_length=17, max_length=17),
):
    decoded = integration_service.decode_vin(vin)
    return VinDecodeResult(**decoded)


@router.get("/vin/{vin}/tree", response_model=VinTreeResponse)
async def get_vehicle_tree(
    vin: str = Path(..., min_length=17, max_length=17),
):
    decoded = integration_service.decode_vin(vin)
    tree = integration_service.get_vehicle_tree(vin)
    return VinTreeResponse(
        vin=vin,
        vehicle=VinDecodeResult(**decoded),
        tree=[VinTreeNode(**node) for node in tree],
    )


@router.get("/vin/{vin}/sections/{section_id}/products")
async def get_vin_section_products(
    vin: str = Path(..., min_length=17, max_length=17),
    section_id: str = Path(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    tree = integration_service.get_vehicle_tree(vin)

    section_keywords: List[str] = []
    for group in tree:
        for child in group.get("children", []):
            if child.get("id") == section_id:
                section_keywords = child.get("keywords", [])
                break
        if section_keywords:
            break

    if not section_keywords:
        for group in tree:
            if group.get("id") == section_id:
                section_keywords = group.get("keywords", [])
                break

    if not section_keywords:
        raise HTTPException(status_code=404, detail=Msg.SECTION_NOT_FOUND)

    decoded = integration_service.decode_vin(vin)
    brand_name = decoded.get("brand", "")

    query = select(Product).where(Product.is_active == True)
    keyword_clauses = []
    for kw in section_keywords:
        keyword_clauses.append(Product.name.ilike(f"%{kw}%"))
        keyword_clauses.append(Product.applicability.ilike(f"%{kw}%"))
    if brand_name and brand_name != "Unknown":
        keyword_clauses.append(Product.applicability.ilike(f"%{brand_name}%"))

    if keyword_clauses:
        query = query.where(or_(*keyword_clauses))

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    products = result.scalars().all()

    sample_products = []
    for p in products[:20]:
        sample_products.append({
            "id": p.id,
            "article": p.article,
            "name": p.name,
            "price": p.price,
            "stock_quantity": p.stock_quantity,
            "stock_status": p.stock_status.value if hasattr(p.stock_status, "value") else str(p.stock_status),
        })

    return VinSearchResult(
        section_id=section_id,
        section_name=_section_name_by_id(tree, section_id),
        keywords=section_keywords,
        products_count=total,
        sample_products=sample_products,
    )


def _section_name_by_id(tree: List[dict], section_id: str) -> str:
    for group in tree:
        if group.get("id") == section_id:
            return group.get("name", section_id)
        for child in group.get("children", []):
            if child.get("id") == section_id:
                return child.get("name", section_id)
    return section_id
