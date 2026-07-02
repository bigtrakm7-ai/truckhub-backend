from datetime import datetime
import csv
import io
import uuid
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.enums import OrderStatus, UserRole
from app.core.rbac import require_roles
from app.models.order import Order, OrderItem
from app.models.product import Product, StockStatus
from app.models.supplier import PriceUpload, Supplier, SupplierAnalytics, SupplierBalance
from app.models.user import User
from app.models.warranty import NotificationSettings
from app.services import integration_service
from app.core.messages import Msg
from app.schemas.supplier import (
    PriceUploadResponse,
    SupplierAnalyticsResponse,
    SupplierBalanceResponse,
    SupplierBulkProductsUpdate,
    SupplierFinanceResponse,
    SupplierProductCreate,
    SupplierProductResponse,
    SupplierProductsListResponse,
    SupplierProductUpdate,
)

router = APIRouter(prefix="/supplier", tags=["Поставщик"])


class PriceUploadUrlRequest(BaseModel):
    url: HttpUrl


def parse_float_value(value: str | None) -> float:
    normalized = (value or "").strip().replace(" ", "").replace(",", ".")
    if not normalized:
        return 0.0
    return float(normalized)


def parse_int_value(value: str | None, default: int = 0) -> int:
    normalized = (value or "").strip().replace(" ", "")
    if not normalized:
        return default
    return int(float(normalized.replace(",", ".")))


def get_row_value(row: dict, names: list[str]) -> str:
    lowered = {str(key).strip().lower(): value for key, value in row.items() if key is not None}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return str(value).strip()
    return ""


def detect_delimiter(sample: str) -> str:
    first_line = sample.splitlines()[0] if sample.splitlines() else ""
    semicolons = first_line.count(";")
    commas = first_line.count(",")
    return ";" if semicolons >= commas else ","


async def get_supplier(current_user: User, db: AsyncSession) -> Supplier:
    result = await db.execute(select(Supplier).where(Supplier.user_id == current_user.id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        supplier = Supplier(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            company_name=current_user.company_name or current_user.email,
            inn=current_user.inn or f"TMP{current_user.id.replace('-', '')[:10]}",
            address=current_user.address,
            warehouse_address=current_user.address,
            is_verified=False,
        )
        db.add(supplier)
        await db.commit()
        await db.refresh(supplier)
    return supplier


async def process_csv_upload(
    supplier: Supplier,
    filename: str,
    content: bytes,
    db: AsyncSession,
    import_kind: str = "products",
) -> PriceUploadResponse:
    from app.services.price_parsers import parse_file, detect_format

    fmt = detect_format(filename)
    upload = PriceUpload(
        id=str(uuid.uuid4()),
        supplier_id=supplier.id,
        filename=filename,
        format=fmt.lstrip(".") if fmt else "unknown",
        import_kind=import_kind,
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)

    updated = 0
    new = 0
    errors = 0
    seen_products: dict[str, Product | None] = {}

    try:
        products_data = parse_file(content, filename, encoding="utf-8-sig", delimiter=";")

        if not products_data:
            decoded_content = content.decode("utf-8-sig", errors="replace")
            sample = decoded_content[:4096]
            dialect = csv.excel
            dialect.delimiter = detect_delimiter(sample)
            reader = csv.DictReader(io.StringIO(decoded_content), dialect=dialect)

            for row in reader:
                try:
                    name = get_row_value(row, ["name", "наименование", "товар", "услуга", "service"])
                    article = get_row_value(row, ["article", "артикул", "sku", "код", "id"])
                    category = get_row_value(row, ["категория", "category"])
                    note = get_row_value(row, ["примечание", "описание", "description", "comment"])

                    if not article:
                        base_name = name or note or category
                        if not base_name:
                            errors += 1
                            continue
                        article = f"EXT-{abs(hash(base_name.lower())) % 10_000_000}"

                    product_name = name or note or article
                    price = parse_float_value(get_row_value(row, ["price", "цена", "стоимость"]))
                    quantity = parse_int_value(
                        get_row_value(row, ["quantity", "остаток", "количество", "qty", "stock"]),
                        default=1,
                    )
                    stock_status = StockStatus.IN_STOCK if quantity > 0 else StockStatus.OUT_OF_STOCK

                    products_data.append({
                        "article": article,
                        "name": product_name,
                        "price": price,
                        "stock_quantity": quantity,
                        "stock_status": stock_status,
                        "category": category,
                        "description": note,
                    })
                except Exception:
                    errors += 1

        for item_data in products_data:
            try:
                article = str(item_data.get("article", "")).strip()
                if not article:
                    errors += 1
                    continue

                product_name = item_data.get("name", article)
                price = float(item_data.get("price", 0) or 0)
                quantity = int(item_data.get("stock_quantity", 1) or 1)
                stock_status = StockStatus.IN_STOCK if quantity > 0 else StockStatus.OUT_OF_STOCK

                product = seen_products.get(article)
                if article not in seen_products:
                    with db.no_autoflush:
                        result = await db.execute(select(Product).where(Product.article == article))
                    product = result.scalar_one_or_none()
                    seen_products[article] = product

                if product:
                    product.supplier_id = supplier.id
                    product.price = price
                    product.stock_quantity = quantity
                    product.name = str(product_name) if product_name else product.name
                    product.stock_status = stock_status
                    if item_data.get("description"):
                        product.description = str(item_data["description"])
                    if item_data.get("brand"):
                        product.brand = str(item_data["brand"])
                    if item_data.get("applicability"):
                        product.applicability = str(item_data["applicability"])
                    updated += 1
                else:
                    product = Product(
                        id=str(uuid.uuid4()),
                        article=article,
                        name=str(product_name),
                        description=str(item_data.get("description", "")),
                        price=price,
                        stock_quantity=quantity,
                        stock_status=stock_status,
                        supplier_id=supplier.id,
                        brand=str(item_data.get("brand", "")) or None,
                        applicability=str(item_data.get("applicability", "")) or None,
                        weight=float(item_data.get("weight", 0) or 0) or None,
                        category_id=item_data.get("category") or None,
                    )
                    db.add(product)
                    seen_products[article] = product
                    new += 1
            except Exception:
                errors += 1

    except Exception as exc:
        upload.status = "failed"
        upload.errors = errors + 1
        upload.completed_at = datetime.utcnow()
        await db.commit()
        raise HTTPException(status_code=400, detail=Msg.parsing_error_detail(exc))

    upload.total_products = updated + new
    upload.updated_products = updated
    upload.new_products = new
    upload.errors = errors
    upload.status = "completed"
    upload.completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(upload)
    return PriceUploadResponse.model_validate(upload)


@router.get("/products", response_model=SupplierProductsListResponse)
async def list_supplier_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)

    base_query = select(Product).where(Product.supplier_id == supplier.id)

    if search:
        base_query = base_query.where(Product.article.ilike(f"%{search}%") | Product.name.ilike(f"%{search}%"))
    if is_active is not None:
        base_query = base_query.where(Product.is_active == is_active)

    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar() or 0

    query = base_query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    products = result.scalars().all()

    responses = []
    for product in products:
        analytics_result = await db.execute(
            select(SupplierAnalytics).where(
                SupplierAnalytics.supplier_id == supplier.id,
                SupplierAnalytics.product_id == product.id,
            )
        )
        analytics = analytics_result.scalars().all()
        views = sum(item.views_count for item in analytics)
        orders = sum(item.orders_count for item in analytics)
        conversion = (orders / views * 100) if views > 0 else 0.0

        responses.append(
            SupplierProductResponse(
                id=product.id,
                article=product.article,
                name=product.name,
                price=product.price,
                stock_quantity=product.stock_quantity,
                stock_status=product.stock_status.value,
                views_count=views,
                orders_count=orders,
                conversion_rate=conversion,
                is_active=product.is_active,
            )
        )

    return SupplierProductsListResponse(
        items=responses,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("/products", response_model=SupplierProductResponse)
async def create_supplier_product(
    data: SupplierProductCreate,
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)

    existing_result = await db.execute(select(Product).where(Product.article == data.article))
    existing_product = existing_result.scalar_one_or_none()
    if existing_product:
        raise HTTPException(status_code=400, detail=Msg.PRODUCT_ARTICLE_EXISTS)

    product = Product(
        id=str(uuid.uuid4()),
        article=data.article.strip(),
        name=data.name.strip(),
        description=(data.description or "").strip() or None,
        price=data.price,
        stock_quantity=data.stock_quantity,
        stock_status=StockStatus.IN_STOCK if data.stock_quantity > 0 else StockStatus.OUT_OF_STOCK,
        supplier_id=supplier.id,
        is_active=data.is_active,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)

    return SupplierProductResponse(
        id=product.id,
        article=product.article,
        name=product.name,
        price=product.price,
        stock_quantity=product.stock_quantity,
        stock_status=product.stock_status.value,
        views_count=0,
        orders_count=0,
        conversion_rate=0.0,
        is_active=product.is_active,
    )


@router.put("/products/{product_id}")
async def update_product(
    product_id: str,
    data: SupplierProductUpdate,
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)
    result = await db.execute(select(Product).where(Product.id == product_id, Product.supplier_id == supplier.id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=Msg.PRODUCT_NOT_FOUND)

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    if "stock_quantity" in update_data:
        product.stock_status = StockStatus.IN_STOCK if (product.stock_quantity or 0) > 0 else StockStatus.OUT_OF_STOCK

    await db.commit()
    await db.refresh(product)
    return SupplierProductResponse(
        id=product.id,
        article=product.article,
        name=product.name,
        price=product.price,
        stock_quantity=product.stock_quantity,
        stock_status=product.stock_status.value,
        views_count=0,
        orders_count=0,
        conversion_rate=0.0,
        is_active=product.is_active,
    )


@router.put("/products/bulk")
async def bulk_update_products(
    data: SupplierBulkProductsUpdate,
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)

    if not data.product_ids:
        raise HTTPException(status_code=400, detail=Msg.NO_PRODUCT_IDS)

    result = await db.execute(
        select(Product).where(
            Product.supplier_id == supplier.id,
            Product.id.in_(data.product_ids),
        )
    )
    products = result.scalars().all()

    if not products:
        raise HTTPException(status_code=404, detail=Msg.PRODUCTS_NOT_FOUND)

    updated_fields = data.dict(exclude_unset=True, exclude={"product_ids"})
    if not updated_fields:
        raise HTTPException(status_code=400, detail=Msg.NO_UPDATE_FIELDS)

    for product in products:
        for field, value in updated_fields.items():
            setattr(product, field, value)
        if "stock_quantity" in updated_fields:
            product.stock_status = StockStatus.IN_STOCK if (product.stock_quantity or 0) > 0 else StockStatus.OUT_OF_STOCK

    await db.commit()

    return {
        "updated": len(products),
        "product_ids": [product.id for product in products],
    }


@router.delete("/products/{product_id}")
async def archive_product(
    product_id: str,
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)
    result = await db.execute(select(Product).where(Product.id == product_id, Product.supplier_id == supplier.id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=Msg.PRODUCT_NOT_FOUND)

    product.is_active = False
    await db.commit()

    return {"message": Msg.PRODUCT_ARCHIVED, "id": product.id}


@router.post("/prices/upload", response_model=PriceUploadResponse)
async def upload_price_list(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)

    if not file.filename:
        raise HTTPException(status_code=400, detail=Msg.FILENAME_REQUIRED)

    file_format = file.filename.split(".")[-1].lower()
    if file_format != "csv":
        raise HTTPException(status_code=400, detail=Msg.CSV_ONLY)

    content = await file.read()
    return await process_csv_upload(supplier, file.filename, content, db, import_kind="products")


@router.post("/prices/upload-by-url", response_model=PriceUploadResponse)
async def upload_price_list_by_url(
    payload: PriceUploadUrlRequest,
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)
    url = str(payload.url)

    if ".csv" not in url.lower():
        raise HTTPException(status_code=400, detail=Msg.CSV_URL_REQUIRED)

    download_error: httpx.HTTPError | None = None
    response_content: bytes | None = None
    for _attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                response_content = response.content
                download_error = None
                break
        except httpx.HTTPError as exc:
            download_error = exc

    if response_content is None:
        raise HTTPException(
            status_code=400,
            detail=Msg.csv_download_error(str(download_error) if download_error else None),
        )

    filename = url.rstrip("/").split("/")[-1] or f"prices-{supplier.id}.csv"
    lowered_url = url.lower()
    import_kind = "services" if "service" in lowered_url or "uslug" in lowered_url else "products"
    return await process_csv_upload(supplier, filename, response_content, db, import_kind=import_kind)


@router.get("/prices/uploads", response_model=List[PriceUploadResponse])
async def list_price_uploads(
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)
    result = await db.execute(
        select(PriceUpload).where(PriceUpload.supplier_id == supplier.id).order_by(PriceUpload.created_at.desc()).limit(10)
    )
    uploads = result.scalars().all()
    return [PriceUploadResponse.model_validate(upload) for upload in uploads]


@router.get("/finance", response_model=SupplierFinanceResponse)
async def get_finance(
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)
    pending_result = await db.execute(
        select(func.sum(OrderItem.total_price)).where(OrderItem.supplier_id == supplier.id, Order.status == OrderStatus.SHIPPED)
    )
    pending_amount = pending_result.scalar() or 0.0

    earned_result = await db.execute(
        select(func.sum(OrderItem.total_price)).where(OrderItem.supplier_id == supplier.id, Order.status == OrderStatus.DELIVERED)
    )
    total_earned = earned_result.scalar() or 0.0

    transactions_result = await db.execute(
        select(SupplierBalance).where(SupplierBalance.supplier_id == supplier.id).order_by(SupplierBalance.created_at.desc()).limit(20)
    )
    transactions = transactions_result.scalars().all()

    return SupplierFinanceResponse(
        balance=supplier.balance,
        pending_amount=pending_amount,
        available_amount=supplier.balance,
        total_earned=total_earned,
        total_commission=total_earned * supplier.commission_rate,
        transactions=[SupplierBalanceResponse.model_validate(item) for item in transactions],
    )


@router.post("/finance/withdraw")
async def request_withdraw(
    amount: float,
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)
    if amount > supplier.balance:
        raise HTTPException(status_code=400, detail=Msg.INSUFFICIENT_BALANCE)

    db.add(
        SupplierBalance(
            id=str(uuid.uuid4()),
            supplier_id=supplier.id,
            amount=-amount,
            transaction_type="withdraw",
            description="Запрос на вывод средств",
            balance_before=supplier.balance,
            balance_after=supplier.balance - amount,
        )
    )

    supplier.balance -= amount
    await db.commit()
    return {"message": Msg.WITHDRAW_SUBMITTED, "new_balance": supplier.balance}


@router.get("/analytics", response_model=SupplierAnalyticsResponse)
async def get_analytics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)
    analytics_result = await db.execute(select(SupplierAnalytics).where(SupplierAnalytics.supplier_id == supplier.id))
    analytics = analytics_result.scalars().all()

    total_views = sum(item.views_count for item in analytics)
    total_orders = sum(item.orders_count for item in analytics)

    products_result = await db.execute(select(Product).where(Product.supplier_id == supplier.id))
    products = products_result.scalars().all()

    top_products = [
        SupplierProductResponse(
            id=item.id,
            article=item.article,
            name=item.name,
            price=item.price,
            stock_quantity=item.stock_quantity,
            stock_status=item.stock_status.value,
            views_count=0,
            orders_count=0,
            conversion_rate=0.0,
            is_active=item.is_active,
        )
        for item in products[:5]
    ]

    conversion = (total_orders / total_views * 100) if total_views > 0 else 0.0

    return SupplierAnalyticsResponse(
        total_views=total_views,
        total_orders=total_orders,
        total_revenue=sum(item.price * 10 for item in products),
        conversion_rate=conversion,
        top_products=top_products,
        views_by_day=[],
    )


@router.get("/orders")
async def list_supplier_orders(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)
    query = select(Order, OrderItem).join(OrderItem).where(OrderItem.supplier_id == supplier.id)
    if status:
        query = query.where(Order.status == status)

    query = query.distinct().offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    rows = result.all()

    product_ids = {item.product_id for _, item in rows}
    product_names: dict[str, str] = {}
    if product_ids:
        products_result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
        product_names = {product.id: product.name for product in products_result.scalars().all()}

    return [
        {
            "order_id": order.id,
            "order_item_id": item.id,
            "order_number": order.order_number,
            "status": item.shipment_status or order.status.value,
            "order_status": order.status.value,
            "total": item.total_price,
            "quantity": item.quantity,
            "product_name": product_names.get(item.product_id, item.product_id),
            "buyer_name": order.buyer_name,
            "buyer_phone": order.buyer_phone,
            "recipient_name": order.recipient_name,
            "recipient_phone": order.recipient_phone,
            "delivery_address": order.delivery_address,
            "delivery_method": order.delivery_method,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "supplier_name": item.supplier_name,
            "tracking_number": item.shipment_tracking_number or order.tracking_number,
            "created_at": order.created_at.isoformat(),
        }
        for order, item in rows
    ]


@router.put("/orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    status: str,
    order_item_id: Optional[str] = None,
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    supplier = await get_supplier(current_user, db)
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=Msg.ORDER_NOT_FOUND)

    items_query = select(OrderItem).where(OrderItem.order_id == order.id, OrderItem.supplier_id == supplier.id)
    if order_item_id:
        items_query = items_query.where(OrderItem.id == order_item_id)
    items_result = await db.execute(items_query)
    target_items = items_result.scalars().all()
    if not target_items:
        raise HTTPException(status_code=404, detail=Msg.SHIPMENT_ITEM_NOT_FOUND)

    target_status = status.lower().strip()

    if target_status == "shipped":
        for item in target_items:
            item.shipment_status = "shipped"
            if not item.shipment_tracking_number:
                item.shipment_tracking_number = f"TH-TRK-{order.order_number[-6:]}-{item.id[:4]}"
    elif target_status == "cancelled":
        for item in target_items:
            item.shipment_status = "cancelled"
    else:
        raise HTTPException(status_code=400, detail=Msg.INVALID_STATUS)

    all_items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    all_items = all_items_result.scalars().all()
    statuses = {(item.shipment_status or "pending").lower() for item in all_items}
    if statuses == {"cancelled"}:
        order.status = OrderStatus.CANCELLED
    elif statuses.issubset({"delivered"}):
        order.status = OrderStatus.DELIVERED
    elif "shipped" in statuses or "delivered" in statuses:
        order.status = OrderStatus.SHIPPED
    else:
        order.status = OrderStatus.PENDING

    if not order.tracking_number:
        first_tracking = next((item.shipment_tracking_number for item in all_items if item.shipment_tracking_number), None)
        order.tracking_number = first_tracking

    await db.commit()

    buyer_result = await db.execute(select(User).where(User.id == order.user_id))
    buyer = buyer_result.scalar_one_or_none()
    if buyer:
        settings_result = await db.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == buyer.id)
        )
        notification_settings = settings_result.scalar_one_or_none()
        integration_service.notify_with_preferences(
            email=buyer.email,
            phone=buyer.phone,
            telegram_chat_id=notification_settings.telegram_chat_id if notification_settings else None,
            email_enabled=notification_settings.email_enabled if notification_settings else True,
            sms_enabled=notification_settings.sms_enabled if notification_settings else False,
            telegram_enabled=notification_settings.telegram_enabled if notification_settings else False,
            message=Msg.order_status_changed(order.order_number, order.status.value),
        )

    return {
        "message": Msg.STATUS_UPDATED,
        "order_id": order.id,
        "order_number": order.order_number,
        "status": order.status.value,
        "tracking_number": order.tracking_number,
    }


# === PAYOUTS ===

@router.get("/payouts/balance")
async def get_payout_balance(
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    from app.services.payout_service import PayoutService
    supplier = await get_supplier(current_user, db)
    return await PayoutService.get_supplier_balance(supplier.id, db)


@router.post("/payouts/request")
async def request_payout(
    period_start: str = Query(...),
    period_end: str = Query(...),
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    from app.services.payout_service import PayoutService
    supplier = await get_supplier(current_user, db)
    return await PayoutService.create_payout_request(
        supplier_id=supplier.id,
        amount=0,
        period_start=datetime.fromisoformat(period_start),
        period_end=datetime.fromisoformat(period_end),
        db=db,
    )


@router.get("/payouts/reconcile")
async def reconcile_payouts(
    period_start: str = Query(...),
    period_end: str = Query(...),
    current_user: User = Depends(require_roles(UserRole.SUPPLIER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    from app.services.payout_service import PayoutService
    supplier = await get_supplier(current_user, db)
    return await PayoutService.reconcile(
        supplier_id=supplier.id,
        period_start=datetime.fromisoformat(period_start),
        period_end=datetime.fromisoformat(period_end),
        db=db,
    )
