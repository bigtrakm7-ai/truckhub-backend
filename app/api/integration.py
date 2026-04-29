from app.services import integration_service
from app.services.notification_schema import validate_notification_payload
from app.services.delivery_schema import validate_delivery_payload
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime
import uuid
import csv
import io

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.user import User
from app.models.product import Product
from app.models.order import Order, OrderItem
from app.api.auth import get_current_active_user

logger = get_logger(__name__)
router = APIRouter(prefix="/integration", tags=["1C Integration"])


@router.post("/1c/upload/catalog")
async def upload_catalog_from_1c(
    file: UploadFile = File(...),
    admin: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename.endswith((".csv", ".xml")):
        raise HTTPException(status_code=400, detail="Only CSV and XML formats supported")

    content = await file.read()

    imported = 0
    updated = 0
    errors = 0

    if file.filename.endswith(".csv"):
        decoded = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))

        for row in reader:
            try:
                article = row.get("article", "").strip()
                if not article:
                    errors += 1
                    continue

                result = await db.execute(select(Product).where(Product.article == article))
                product = result.scalar_one_or_none()

                if product:
                    product.name = row.get("name", product.name)
                    product.price = float(row.get("price", product.price))
                    product.stock_quantity = int(row.get("quantity", product.stock_quantity))
                    updated += 1
                else:
                    new_product = Product(
                        id=str(uuid.uuid4()),
                        article=article,
                        name=row.get("name", article),
                        price=float(row.get("price", 0)),
                        stock_quantity=int(row.get("quantity", 0)),
                    )
                    db.add(new_product)
                    imported += 1
            except Exception:
                errors += 1

    await db.commit()

    return {"message": "Import completed", "imported": imported, "updated": updated, "errors": errors}


@router.get("/1c/export/orders")
async def export_orders_to_1c(
    date_from: str = Query(...),
    date_to: str = Query(...),
    admin: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from_date = datetime.fromisoformat(date_from)
    to_date = datetime.fromisoformat(date_to)

    result = await db.execute(
        select(Order).where(Order.created_at >= from_date, Order.created_at <= to_date).order_by(Order.created_at)
    )
    orders = result.scalars().all()

    export_data = []
    for order in orders:
        items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        items = items_result.scalars().all()

        for item in items:
            export_data.append(
                {
                    "order_id": order.order_number,
                    "date": order.created_at.isoformat(),
                    "customer_email": order.user_id,
                    "product_article": item.product_id,
                    "quantity": item.quantity,
                    "price": item.unit_price,
                    "total": item.total_price,
                }
            )

    return {"orders": export_data, "count": len(export_data)}


@router.get("/1c/export/stock")
async def export_stock_to_1c(
    admin: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.is_active == True))
    products = result.scalars().all()

    export_data = []
    for p in products:
        export_data.append(
            {
                "article": p.article,
                "name": p.name,
                "quantity": p.stock_quantity,
                "price": p.price,
                "reserved": 0,
            }
        )

    return {"products": export_data, "count": len(export_data)}


@router.post("/1c/sync/stock")
async def sync_stock_from_1c(
    data: List[dict],
    admin: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    updated = 0
    for item in data:
        article = item.get("article")
        quantity = item.get("quantity", 0)

        result = await db.execute(select(Product).where(Product.article == article))
        product = result.scalar_one_or_none()
        if product:
            product.stock_quantity = quantity
            updated += 1

    await db.commit()
    return {"message": f"Synced {updated} products", "updated": updated}


@router.get("/providers/health")
async def providers_health(
    admin: User = Depends(get_current_active_user),
):
    return integration_service.providers_health()


@router.post("/delivery/estimate")
async def delivery_estimate(
    payload: dict,
    user: User = Depends(get_current_active_user),
):
    try:
        req = validate_delivery_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    try:
        return integration_service.estimate_delivery(req.__dict__)
    except ValueError as exc:
        logger.warning("delivery_estimate_failed", extra={"extra": {"error": str(exc)}})
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception("delivery_estimate_unexpected")
        raise HTTPException(status_code=502, detail="delivery provider unavailable")


@router.get("/catalog/vin/{vin}")
async def catalog_vin_decode(
    vin: str,
    user: User = Depends(get_current_active_user),
):
    return integration_service.decode_vin(vin)


@router.get("/catalog/vin/{vin}/tree")
async def catalog_vin_tree(
    vin: str,
    user: User = Depends(get_current_active_user),
):
    decoded = integration_service.decode_vin(vin)
    tree = integration_service.get_vehicle_tree(vin)
    return {"vin": vin, "vehicle": decoded, "tree": tree}


@router.post("/notifications/send")
async def send_notification(
    payload: dict,
    user: User = Depends(get_current_active_user),
):
    try:
        p = validate_notification_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    result = integration_service.send_notification(channel=p.channel, to=p.to, message=p.message)
    if result.get("status") == "failed":
        logger.warning(
            "notification_send_failed",
            extra={"extra": {"channel": p.channel, "to": p.to, "error": result.get("error", "")}},
        )
        raise HTTPException(status_code=502, detail="notification provider unavailable")

    return result
