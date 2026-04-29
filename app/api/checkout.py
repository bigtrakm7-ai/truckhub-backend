from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime
import uuid

from app.core.database import get_db
from app.core.enums import OrderStatus, PaymentStatus
from app.models.user import User
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.order import Order, OrderItem
from app.models.checkout import Cart, CartItem, DeliveryRequest
from app.models.warranty import NotificationSettings
from app.schemas.checkout import (
    CartItemCreate, CartResponse, CartItemResponse,
    DeliveryEstimate, CheckoutData, OrderCreateResponse, DeliveryPoint
)
from app.api.auth import get_current_active_user
from app.services import integration_service

router = APIRouter(prefix="/checkout", tags=["Checkout"])


async def get_or_create_cart(user_id: str, db: AsyncSession) -> Cart:
    result = await db.execute(select(Cart).where(Cart.user_id == user_id))
    cart = result.scalar_one_or_none()
    if not cart:
        cart = Cart(id=str(uuid.uuid4()), user_id=user_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)
    return cart


@router.get("/cart", response_model=CartResponse)
async def get_cart(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    cart = await get_or_create_cart(current_user.id, db)
    
    result = await db.execute(
        select(CartItem).where(CartItem.cart_id == cart.id)
    )
    items = result.scalars().all()
    
    cart_items = []
    suppliers = set()
    subtotal = 0.0
    
    for item in items:
        product_result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = product_result.scalar_one_or_none()
        if not product:
            continue
        
        supplier_name = "TruckHub"
        if product.supplier_id:
            sup_result = await db.execute(select(Supplier).where(Supplier.id == product.supplier_id))
            sup = sup_result.scalar_one_or_none()
            if sup:
                supplier_name = sup.company_name
                suppliers.add(supplier_name)
        
        unit_price = product.price
        total_price = unit_price * item.quantity
        subtotal += total_price
        
        delivery_days = 1 if product.stock_quantity > 0 else 14
        
        cart_items.append(CartItemResponse(
            id=item.id,
            product_id=product.id,
            product_name=product.name,
            product_article=product.article,
            supplier_id=product.supplier_id or "",
            supplier_name=supplier_name,
            quantity=item.quantity,
            unit_price=unit_price,
            total_price=total_price,
            stock_status=product.stock_status.value,
            delivery_days=delivery_days
        ))
    
    delivery_price = 0.0
    if len(suppliers) > 1:
        delivery_price = 500
    
    return CartResponse(
        id=cart.id,
        items=cart_items,
        items_count=len(items),
        subtotal=subtotal,
        delivery_price=delivery_price,
        total_price=subtotal + delivery_price,
        suppliers=list(suppliers)
    )


@router.post("/cart/items")
async def add_to_cart(
    item: CartItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    cart = await get_or_create_cart(current_user.id, db)
    
    result = await db.execute(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.product_id == item.product_id
        )
    )
    existing_item = result.scalar_one_or_none()
    
    if existing_item:
        existing_item.quantity += item.quantity
    else:
        new_item = CartItem(
            id=str(uuid.uuid4()),
            cart_id=cart.id,
            product_id=item.product_id,
            quantity=item.quantity
        )
        db.add(new_item)
    
    await db.commit()
    return {"message": "Item added to cart"}


@router.put("/cart/items/{item_id}")
async def update_cart_item(
    item_id: str,
    quantity: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    cart = await get_or_create_cart(current_user.id, db)
    
    result = await db.execute(
        select(CartItem).where(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    
    if quantity <= 0:
        await db.delete(item)
    else:
        item.quantity = quantity
    
    await db.commit()
    return {"message": "Cart updated"}


@router.delete("/cart/items/{item_id}")
async def remove_from_cart(
    item_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    cart = await get_or_create_cart(current_user.id, db)
    
    result = await db.execute(
        select(CartItem).where(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    
    await db.delete(item)
    await db.commit()
    return {"message": "Item removed from cart"}


@router.delete("/cart")
async def clear_cart(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    cart = await get_or_create_cart(current_user.id, db)
    
    result = await db.execute(
        select(CartItem).where(CartItem.cart_id == cart.id)
    )
    items = result.scalars().all()
    for item in items:
        await db.delete(item)
    
    await db.commit()
    return {"message": "Cart cleared"}


@router.get("/delivery/estimates", response_model=List[DeliveryEstimate])
async def get_delivery_estimates(
    city: str = Query(...),
    weight: float = Query(1.0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    estimates = [
        DeliveryEstimate(
            method="courier",
            name="Курьер TruckHub",
            price=350 if weight < 5 else 600,
            days_min=1,
            days_max=2,
            logo="🚚"
        ),
        DeliveryEstimate(
            method="sdek",
            name="СДЭК",
            price=450 if weight < 5 else 800,
            days_min=2,
            days_max=4,
            logo="📦"
        ),
        DeliveryEstimate(
            method="delovye_linii",
            name="Деловые Линии",
            price=550 if weight < 5 else 950,
            days_min=3,
            days_max=5,
            logo="🚛"
        ),
        DeliveryEstimate(
            method="pek",
            name="ПЭК",
            price=650 if weight < 5 else 1100,
            days_min=3,
            days_max=6,
            logo="🛻"
        ),
    ]
    return estimates


@router.get("/delivery/points")
async def get_pickup_points(
    city: str = Query(...),
    current_user: User = Depends(get_current_active_user)
):
    points = [
        DeliveryPoint(
            id="1",
            name="Пункт выдачи Москва",
            address="ул. Транспортная, д. 15",
            city="Москва",
            work_hours="Пн-Пт 9:00-20:00, Сб 10:00-18:00"
        ),
        DeliveryPoint(
            id="2",
            name="Пункт выдачи Санкт-Петербург",
            address="пр. Энгельса, д. 100",
            city="Санкт-Петербург",
            work_hours="Пн-Пт 9:00-20:00"
        ),
    ]
    return [p for p in points if city.lower() in p.city.lower()]


@router.post("/order", response_model=OrderCreateResponse)
async def create_order(
    checkout_data: CheckoutData,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    cart = await get_or_create_cart(current_user.id, db)
    
    result = await db.execute(
        select(CartItem).where(CartItem.cart_id == cart.id)
    )
    items = result.scalars().all()
    
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    order_id = str(uuid.uuid4())
    order_number = f"TH-{datetime.now().strftime('%Y%m%d')}-{order_id[:8].upper()}"
    
    subtotal = 0.0
    order_items = []
    
    for item in items:
        product_result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = product_result.scalar_one_or_none()
        if not product:
            continue
        
        total_price = product.price * item.quantity
        subtotal += total_price
        
        supplier_name = "TruckHub"
        if product.supplier_id:
            supplier_result = await db.execute(select(Supplier).where(Supplier.id == product.supplier_id))
            supplier = supplier_result.scalar_one_or_none()
            if supplier:
                supplier_name = supplier.company_name

        order_item = OrderItem(
            id=str(uuid.uuid4()),
            order_id=order_id,
            product_id=product.id,
            supplier_id=product.supplier_id,
            supplier_name=supplier_name,
            quantity=item.quantity,
            unit_price=product.price,
            total_price=total_price,
        )
        order_items.append(order_item)
        db.add(order_item)
    
    delivery_price = 350.0
    total_price = subtotal + delivery_price
    
    payment_status = "awaiting"
    if checkout_data.payment_method == "invoice":
        payment_status = "processing"

    order = Order(
        id=order_id,
        order_number=order_number,
        user_id=current_user.id,
        status=OrderStatus.PENDING,
        total_amount=total_price,
        delivery_amount=delivery_price,
        delivery_address=checkout_data.delivery_address,
        delivery_method=checkout_data.delivery_method,
        payment_method=checkout_data.payment_method,
        payment_status=payment_status,
        buyer_name=checkout_data.buyer_name or current_user.company_name or current_user.email,
        buyer_phone=checkout_data.buyer_phone or current_user.phone,
        recipient_name=checkout_data.recipient_name or checkout_data.buyer_name or current_user.company_name or current_user.email,
        recipient_phone=checkout_data.recipient_phone or checkout_data.buyer_phone or current_user.phone,
        notes=checkout_data.comment,
    )
    db.add(order)
    
    delivery_request = DeliveryRequest(
        id=str(uuid.uuid4()),
        order_id=order_id,
        method=checkout_data.delivery_method,
        address_to=checkout_data.delivery_address or "",
        price=delivery_price,
    )
    db.add(delivery_request)
    
    for item in items:
        await db.delete(item)
    
    await db.commit()

    notification_settings_result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == current_user.id)
    )
    notification_settings = notification_settings_result.scalar_one_or_none()
    integration_service.notify_with_preferences(
        email=current_user.email,
        phone=current_user.phone,
        telegram_chat_id=notification_settings.telegram_chat_id if notification_settings else None,
        email_enabled=notification_settings.email_enabled if notification_settings else True,
        sms_enabled=notification_settings.sms_enabled if notification_settings else False,
        telegram_enabled=notification_settings.telegram_enabled if notification_settings else False,
        message=f"Order {order_number}: status changed to {OrderStatus.PENDING.value}",
    )

    payment_url = None
    if checkout_data.payment_method == "card_online":
        payment_url = f"https://payment.truckhub.ru/order/{order_number}"
        order.payment_url = payment_url
    elif checkout_data.payment_method == "sbp":
        payment_url = f"https://sbp.truckhub.ru/order/{order_number}"
        order.payment_url = payment_url
    
    return OrderCreateResponse(
        order_id=order_id,
        order_number=order_number,
        total_amount=total_price,
        delivery_price=delivery_price,
        status=OrderStatus.PENDING.value,
        payment_method=checkout_data.payment_method,
        payment_status=payment_status,
        payment_url=payment_url,
        created_at=datetime.utcnow()
    )


@router.get("/order/{order_id}/payment")
async def get_payment_url(
    order_id: str,
    payment_method: str = Query("card_online"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    payment_url = None
    if payment_method == "card_online":
        payment_url = f"https://payment.truckhub.ru/order/{order.order_number}"
    elif payment_method == "sbp":
        payment_url = f"https://sbp.truckhub.ru/order/{order.order_number}"
    
    return {
        "payment_url": payment_url,
        "order_number": order.order_number,
        "amount": order.total_amount
    }


