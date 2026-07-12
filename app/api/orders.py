from collections import defaultdict
from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_active_user
from app.core.config import settings
from app.core.database import get_db
from app.core.enums import OrderStatus
from app.models.order import Order, OrderItem, Shipment, ShipmentStatus
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.order import OrderCreate, OrderListResponse, OrderResponse, OrderUpdate
from app.core.messages import Msg

router = APIRouter(prefix="/orders", tags=["Заказы"])


def _serialize_shipments(items: list[OrderItem], shipments: list[Shipment] | None = None) -> list[dict]:
    shipment_map: dict[str, Shipment] = {}
    if shipments:
        for s in shipments:
            shipment_map[s.id] = s

    grouped: dict[str, dict] = {}

    for item in items:
        shipment_id = getattr(item, "shipment_id", None)
        if shipment_id and shipment_id in shipment_map:
            s = shipment_map[shipment_id]
            key = s.id
            if key not in grouped:
                grouped[key] = {
                    "shipment_id": s.id,
                    "supplier_id": s.supplier_id,
                    "supplier_name": s.supplier_name or "Не указан",
                    "status": s.status,
                    "tracking_number": s.tracking_number,
                    "delivery_provider": s.delivery_provider,
                    "delivery_price": s.delivery_price,
                    "delivery_days_min": s.delivery_days_min,
                    "delivery_days_max": s.delivery_days_max,
                    "weight_kg": s.weight_kg,
                    "items_count": 0,
                    "total_amount": 0.0,
                    "items": [],
                }
            grouped[key]["items_count"] += 1
            grouped[key]["total_amount"] += item.total_price
            grouped[key]["items"].append({
                "id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
                "is_installation": item.is_installation,
            })
        else:
            supplier_key = item.supplier_id or "unknown"
            shipment = grouped.get(supplier_key)
            if shipment is None:
                shipment = {
                    "shipment_id": None,
                    "supplier_id": item.supplier_id,
                    "supplier_name": item.supplier_name or "Не указан",
                    "status": item.shipment_status or "pending",
                    "tracking_number": item.shipment_tracking_number,
                    "items_count": 0,
                    "total_amount": 0.0,
                    "items": [],
                }
                grouped[supplier_key] = shipment

            shipment["items_count"] += 1
            shipment["total_amount"] += item.total_price
            shipment["items"].append({
                "id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
                "supplier_name": item.supplier_name,
                "shipment_status": item.shipment_status,
                "shipment_tracking_number": item.shipment_tracking_number,
                "is_installation": item.is_installation,
            })

    return list(grouped.values())


def _calculate_order_status(items: list[OrderItem], fallback_status: OrderStatus) -> OrderStatus:
    if not items:
        return fallback_status

    statuses = {(item.shipment_status or "pending").lower() for item in items}
    if statuses == {"cancelled"}:
        return OrderStatus.CANCELLED
    if statuses.issubset({"delivered"}):
        return OrderStatus.DELIVERED
    if "shipped" in statuses or "delivered" in statuses:
        return OrderStatus.SHIPPED
    return OrderStatus.PENDING


@router.post("/", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    order_id = str(uuid.uuid4())
    order_number = f"TH-{datetime.now().strftime('%Y%m%d')}-{order_id[:8]}"

    order = Order(
        id=order_id,
        order_number=order_number,
        user_id=current_user.id,
        status=OrderStatus.DRAFT,
        delivery_address=order_data.delivery_address,
        delivery_method=order_data.delivery_method,
        notes=order_data.notes,
    )
    db.add(order)

    total_amount = 0.0
    items = []
    supplier_groups: dict[str, dict] = {}

    for item_data in order_data.items:
        result = await db.execute(select(Product).where(Product.id == item_data.product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=Msg.product_not_found_id(item_data.product_id))

        item_total = product.price * item_data.quantity
        total_amount += item_total

        supplier_key = product.supplier_id or "default"
        if supplier_key not in supplier_groups:
            supplier_name = settings.PROJECT_NAME
            if product.supplier_id:
                sup_result = await db.execute(select(Supplier).where(Supplier.id == product.supplier_id))
                sup = sup_result.scalar_one_or_none()
                if sup:
                    supplier_name = sup.company_name
            supplier_groups[supplier_key] = {
                "supplier_id": product.supplier_id,
                "supplier_name": supplier_name,
                "items_data": [],
            }
        supplier_groups[supplier_key]["items_data"].append({
            "product": product,
            "quantity": item_data.quantity,
            "item_total": item_total,
            "is_installation": item_data.is_installation,
            "installation_date": item_data.installation_date,
            "service_center_id": item_data.service_center_id,
        })

    delivery_total = 0.0
    shipments = []

    for supplier_key, group in supplier_groups.items():
        shipment_id = str(uuid.uuid4())
        weight_kg = sum(
            (getattr(d["product"], "weight", None) or 0) * d["quantity"]
            for d in group["items_data"]
        )
        delivery_price = 0.0
        if len(supplier_groups) > 1:
            delivery_price = 350.0 + (weight_kg * 10 if weight_kg > 0 else 0)
        elif weight_kg > 50:
            delivery_price = 350.0 + (weight_kg * 5)

        delivery_total += delivery_price

        shipment = Shipment(
            id=shipment_id,
            order_id=order_id,
            supplier_id=group["supplier_id"],
            supplier_name=group["supplier_name"],
            status=ShipmentStatus.PENDING,
            delivery_price=delivery_price,
            delivery_days_min=1 if weight_kg < 100 else 3,
            delivery_days_max=3 if weight_kg < 100 else 7,
            weight_kg=weight_kg or None,
        )
        db.add(shipment)
        shipments.append(shipment)

        for d in group["items_data"]:
            order_item = OrderItem(
                id=str(uuid.uuid4()),
                order_id=order_id,
                product_id=d["product"].id,
                supplier_id=d["product"].supplier_id,
                shipment_id=shipment_id,
                quantity=d["quantity"],
                unit_price=d["product"].price,
                total_price=d["item_total"],
                shipment_status="pending",
                is_installation=d["is_installation"],
                installation_date=d["installation_date"],
                service_center_id=d["service_center_id"],
            )
            db.add(order_item)
            items.append(order_item)

    order.total_amount = total_amount
    order.delivery_amount = delivery_total
    order.status = OrderStatus.PENDING

    await db.commit()

    for item in items:
        await db.refresh(item)
    for s in shipments:
        await db.refresh(s)

    from app.services.commission_engine import CommissionEngine
    commission_data = await CommissionEngine.calculate_order_commission(order, items, db)
    await db.commit()

    order.items = items
    order.shipments_list = shipments
    order.shipments = _serialize_shipments(items, shipments)
    return order


@router.get("/", response_model=List[OrderListResponse])
async def list_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Order).where(Order.user_id == current_user.id).order_by(Order.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    orders = result.scalars().all()

    order_responses = []
    for order in orders:
        items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        items = items_result.scalars().all()
        shipments_result = await db.execute(select(Shipment).where(Shipment.order_id == order.id))
        shipments = shipments_result.scalars().all()
        derived_status = _calculate_order_status(items, order.status)
        order_responses.append(
            OrderListResponse(
                id=order.id,
                order_number=order.order_number,
                status=derived_status,
                total_amount=order.total_amount,
                delivery_address=order.delivery_address,
                delivery_method=order.delivery_method,
                payment_method=order.payment_method,
                payment_status=order.payment_status,
                buyer_name=order.buyer_name,
                recipient_name=order.recipient_name,
                created_at=order.created_at,
                items_count=len(items),
                shipments_count=len(shipments),
            )
        )

    return order_responses


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=Msg.ORDER_NOT_FOUND)

    items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    items = items_result.scalars().all()

    shipments_result = await db.execute(select(Shipment).where(Shipment.order_id == order.id))
    shipments = shipments_result.scalars().all()

    order.items = items
    order.shipments = _serialize_shipments(items, shipments)
    order.status = _calculate_order_status(items, order.status)
    return order


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: str,
    order_data: OrderUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=Msg.ORDER_NOT_FOUND)

    update_data = order_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(order, field, value)

    await db.commit()
    await db.refresh(order)

    items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    items = items_result.scalars().all()

    shipments_result = await db.execute(select(Shipment).where(Shipment.order_id == order.id))
    shipments = shipments_result.scalars().all()

    order.items = items
    order.shipments = _serialize_shipments(items, shipments)
    order.status = _calculate_order_status(items, order.status)
    return order


@router.get("/{order_id}/shipments")
async def get_order_shipments(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=Msg.ORDER_NOT_FOUND)

    shipments_result = await db.execute(select(Shipment).where(Shipment.order_id == order.id))
    shipments = shipments_result.scalars().all()

    items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    items = items_result.scalars().all()

    result_data = []
    for s in shipments:
        shipment_items = [i for i in items if getattr(i, "shipment_id", None) == s.id]
        product_names = {}
        for i in shipment_items:
            p_result = await db.execute(select(Product).where(Product.id == i.product_id))
            p = p_result.scalar_one_or_none()
            if p:
                product_names[i.id] = p.name

        result_data.append({
            "id": s.id,
            "supplier_id": s.supplier_id,
            "supplier_name": s.supplier_name,
            "status": s.status,
            "tracking_number": s.tracking_number,
            "delivery_provider": s.delivery_provider,
            "delivery_price": s.delivery_price,
            "delivery_days_min": s.delivery_days_min,
            "delivery_days_max": s.delivery_days_max,
            "weight_kg": s.weight_kg,
            "items_count": len(shipment_items),
            "total_amount": sum(i.total_price for i in shipment_items),
            "items": [
                {
                    "id": i.id,
                    "product_id": i.product_id,
                    "product_name": product_names.get(i.id, ""),
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "total_price": i.total_price,
                }
                for i in shipment_items
            ],
            "shipped_at": s.shipped_at.isoformat() if s.shipped_at else None,
            "delivered_at": s.delivered_at.isoformat() if s.delivered_at else None,
        })

    return {"order_id": order_id, "order_number": order.order_number, "shipments": result_data}


@router.put("/{order_id}/shipments/{shipment_id}")
async def update_shipment(
    order_id: str,
    shipment_id: str,
    status: Optional[str] = None,
    tracking_number: Optional[str] = None,
    delivery_provider: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=Msg.ORDER_NOT_FOUND)

    shipment_result = await db.execute(select(Shipment).where(Shipment.id == shipment_id, Shipment.order_id == order_id))
    shipment = shipment_result.scalar_one_or_none()
    if not shipment:
        raise HTTPException(status_code=404, detail=Msg.SHIPMENT_NOT_FOUND)

    if status:
        valid = {"pending", "confirmed", "assembling", "shipped", "in_transit", "delivered", "cancelled"}
        if status not in valid:
            raise HTTPException(status_code=400, detail=Msg.invalid_status_valid(", ".join(valid)))
        shipment.status = status

        items_result = await db.execute(
            select(OrderItem).where(OrderItem.shipment_id == shipment_id)
        )
        for item in items_result.scalars().all():
            item.shipment_status = status
            if status == "shipped" and not item.shipment_tracking_number:
                item.shipment_tracking_number = tracking_number or f"TH-TRK-{order.order_number[-6:]}-{item.id[:4]}"

        if status == "shipped":
            shipment.shipped_at = datetime.utcnow()
        elif status == "delivered":
            shipment.delivered_at = datetime.utcnow()

        all_items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
        all_items = all_items_result.scalars().all()
        order.status = _calculate_order_status(all_items, order.status)

    if tracking_number:
        shipment.tracking_number = tracking_number

    if delivery_provider:
        shipment.delivery_provider = delivery_provider

    await db.commit()
    await db.refresh(shipment)

    return {
        "id": shipment.id,
        "status": shipment.status,
        "tracking_number": shipment.tracking_number,
        "delivery_provider": shipment.delivery_provider,
    }