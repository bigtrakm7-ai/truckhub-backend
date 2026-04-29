from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from app.core.database import get_db
from app.core.enums import OrderStatus, UserRole
from app.models.user import User
from app.models.product import Product, Category
from app.models.order import Order, OrderItem
from app.models.supplier import Supplier
from app.models.admin import Banner, CommissionRule, Dispute, UserVerification, DisputeStatus, DisputeReason
from app.models.warranty import NotificationSettings
from app.schemas.admin import (
    AdminDashboardStats, UserVerificationResponse, CommissionRuleResponse,
    BannerResponse, DisputeResponse, DisputeCreate,
    CommissionRuleCreate, CommissionRuleUpdate, BannerCreate, BannerUpdate
)
from app.api.auth import get_current_active_user
from app.core.rbac import require_roles
from app.services import integration_service

router = APIRouter(prefix="/admin", tags=["Admin"])

async def require_admin(current_user: User = Depends(require_roles(UserRole.ADMIN))) -> User:
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# === DASHBOARD ===

@router.get("/dashboard", response_model=AdminDashboardStats)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    users_count = await db.scalar(select(func.count(User.id)))
    suppliers_count = await db.scalar(select(func.count(Supplier.id)))
    products_count = await db.scalar(select(func.count(Product.id)))
    orders_count = await db.scalar(select(func.count(Order.id)))
    
    revenue = await db.scalar(select(func.sum(Order.total_amount))) or 0.0
    commission = revenue * 0.05
    
    pending_disputes = await db.scalar(
        select(func.count(Dispute.id)).where(Dispute.status == "open")
    ) or 0
    
    pending_verifications = await db.scalar(
        select(func.count(UserVerification.id)).where(UserVerification.status == "pending")
    ) or 0
    
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    
    orders_today = await db.scalar(
        select(func.count(Order.id)).where(Order.created_at >= today_start)
    ) or 0
    
    revenue_today = await db.scalar(
        select(func.sum(Order.total_amount)).where(Order.created_at >= today_start)
    ) or 0.0
    
    return AdminDashboardStats(
        total_users=users_count or 0,
        total_suppliers=suppliers_count or 0,
        total_products=products_count or 0,
        total_orders=orders_count or 0,
        total_revenue=revenue,
        total_commission=commission,
        pending_disputes=pending_disputes,
        pending_verifications=pending_verifications,
        orders_today=orders_today,
        orders_change=12.5,
        revenue_today=revenue_today,
        revenue_change=8.3,
        top_categories=[
            {"name": "Двигатель", "revenue": 450000, "change": 15},
            {"name": "Подвеска", "revenue": 320000, "change": 8},
            {"name": "Тормоза", "revenue": 280000, "change": -3},
        ],
        top_suppliers=[
            {"name": "АвтоЗапчасть ООО", "revenue": 1250000, "orders": 342},
            {"name": "ТрансДеталь", "revenue": 980000, "orders": 256},
            {"name": "ГрузСервис", "revenue": 760000, "orders": 198},
        ]
    )

# === USERS & VERIFICATIONS ===

@router.get("/users", response_model=List[UserVerificationResponse])
async def list_users(
    role: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(User)
    if role:
        normalized_role = role.upper()
        if normalized_role in UserRole.__members__:
            query = query.where(User.role == UserRole[normalized_role])
    query = query.order_by(desc(User.created_at)).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    users = result.scalars().all()
    
    responses = []
    for user in users:
        user_role = user.role.value if hasattr(user.role, "value") else str(user.role)
        responses.append(UserVerificationResponse(
            id=user.id,
            user_id=user.id,
            user_email=user.email,
            user_type=user_role,
            company_name=user.company_name,
            inn=user.inn,
            status="verified" if user.is_verified else "pending",
            created_at=user.created_at
        ))
    return responses

@router.get("/verifications", response_model=List[UserVerificationResponse])
async def list_verifications(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(UserVerification)
    if status:
        query = query.where(UserVerification.status == status)
    query = query.order_by(desc(UserVerification.created_at)).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    verifications = result.scalars().all()
    
    return [UserVerificationResponse(
        id=v.id,
        user_id=v.user_id,
        user_email="user@example.com",
        user_type=v.user_type,
        company_name=None,
        inn=None,
        status=v.status,
        created_at=v.created_at
    ) for v in verifications]

@router.post("/verifications/{verification_id}/approve")
async def approve_verification(
    verification_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(UserVerification).where(UserVerification.id == verification_id))
    verification = result.scalar_one_or_none()
    if not verification:
        raise HTTPException(status_code=404, detail="Verification not found")
    verification.status = "approved"
    verification.verified_by = admin.id
    verification.verified_at = datetime.utcnow()
    await db.commit()
    return {"message": "Verification approved"}

@router.post("/verifications/{verification_id}/reject")
async def reject_verification(
    verification_id: str,
    reason: str = Query(..., min_length=2),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(UserVerification).where(UserVerification.id == verification_id))
    verification = result.scalar_one_or_none()
    if not verification:
        raise HTTPException(status_code=404, detail="Verification not found")
    verification.status = "rejected"
    verification.verified_by = admin.id
    verification.verified_at = datetime.utcnow()
    verification.rejection_reason = reason
    await db.commit()
    return {"message": "Verification rejected"}

# === COMMISSION RULES ===

@router.get("/commissions", response_model=List[CommissionRuleResponse])
async def list_commission_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CommissionRule).order_by(desc(CommissionRule.created_at))
    )
    rules = result.scalars().all()
    responses = []
    for rule in rules:
        responses.append(CommissionRuleResponse(
            id=rule.id,
            name=rule.name,
            category_id=rule.category_id,
            supplier_id=rule.supplier_id,
            commission_percent=rule.commission_percent,
            is_active=rule.is_active,
            created_at=rule.created_at
        ))
    return responses

@router.post("/commissions", response_model=CommissionRuleResponse)
async def create_commission_rule(
    data: CommissionRuleCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    rule = CommissionRule(
        id=str(uuid.uuid4()),
        name=data.name,
        category_id=data.category_id,
        supplier_id=data.supplier_id,
        commission_percent=data.commission_percent,
        is_active=data.is_active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return CommissionRuleResponse.model_validate(rule)

@router.put("/commissions/{rule_id}", response_model=CommissionRuleResponse)
async def update_commission_rule(
    rule_id: str,
    data: CommissionRuleUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(CommissionRule).where(CommissionRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Commission rule not found")
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(rule, key, value)
    rule.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(rule)
    return CommissionRuleResponse.model_validate(rule)

# === BANNERS ===

@router.get("/banners", response_model=List[BannerResponse])
async def list_banners(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Banner).order_by(Banner.sort_order.asc(), desc(Banner.created_at))
    )
    return result.scalars().all()

@router.post("/banners", response_model=BannerResponse)
async def create_banner(
    data: BannerCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    banner = Banner(
        id=str(uuid.uuid4()),
        title=data.title,
        subtitle=data.subtitle,
        image_url=data.image_url,
        link_url=data.link_url,
        position=data.position,
        is_active=data.is_active,
        sort_order=data.sort_order,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(banner)
    await db.commit()
    await db.refresh(banner)
    return BannerResponse.model_validate(banner)

@router.put("/banners/{banner_id}", response_model=BannerResponse)
async def update_banner(
    banner_id: str,
    data: BannerUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Banner).where(Banner.id == banner_id))
    banner = result.scalar_one_or_none()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    for key, value in data.model_dump(exclude_none=True).items():
        setattr(banner, key, value)
    banner.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(banner)
    return BannerResponse.model_validate(banner)

# === ORDERS ===

@router.get("/orders")
async def list_orders(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    query = select(Order).order_by(desc(Order.created_at))
    if status:
        query = query.where(Order.status == status)
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    orders = result.scalars().all()

    response = []
    for order in orders:
        buyer_result = await db.execute(select(User).where(User.id == order.user_id))
        buyer = buyer_result.scalar_one_or_none()
        items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
        items = items_result.scalars().all()

        response.append({
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status.value if hasattr(order.status, "value") else str(order.status),
            "total_amount": order.total_amount,
            "delivery_method": order.delivery_method,
            "delivery_address": order.delivery_address,
            "tracking_number": order.tracking_number,
            "buyer_email": buyer.email if buyer else "unknown",
            "buyer_name": order.buyer_name,
            "buyer_phone": order.buyer_phone,
            "recipient_name": order.recipient_name,
            "recipient_phone": order.recipient_phone,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "items_count": len(items),
            "created_at": order.created_at,
        })
    return response

@router.put("/orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    status: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    normalized = status.lower().strip()
    allowed_statuses = {
        OrderStatus.PENDING.value: OrderStatus.PENDING,
        OrderStatus.PAID.value: OrderStatus.PAID,
        OrderStatus.SHIPPED.value: OrderStatus.SHIPPED,
        OrderStatus.DELIVERED.value: OrderStatus.DELIVERED,
        OrderStatus.CANCELLED.value: OrderStatus.CANCELLED,
    }
    if normalized not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")

    order.status = allowed_statuses[normalized]
    if normalized == OrderStatus.PAID.value:
        order.payment_status = "succeeded"
    if normalized in {OrderStatus.SHIPPED.value, OrderStatus.DELIVERED.value} and not order.tracking_number:
        order.tracking_number = f"TH-ADM-{order.order_number[-6:]}"

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
            message=f"Order {order.order_number}: status changed to {order.status.value}",
        )

    return {
        "message": "Order status updated",
        "order_id": order.id,
        "order_number": order.order_number,
        "status": order.status.value,
        "payment_status": order.payment_status,
        "tracking_number": order.tracking_number,
    }

# === DISPUTES ===

@router.post("/disputes", response_model=DisputeResponse)
async def create_dispute(
    data: DisputeCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    order_result = await db.execute(select(Order).where(Order.id == data.order_id, Order.user_id == current_user.id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    item_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    first_item = item_result.scalars().first()
    supplier_id = first_item.supplier_id if first_item else "system"

    new_dispute = Dispute(
        id=str(uuid.uuid4()),
        order_id=order.id,
        buyer_id=current_user.id,
        supplier_id=supplier_id,
        status=DisputeStatus.OPEN,
        reason=data.reason,
        buyer_description=data.buyer_description,
        created_at=datetime.utcnow()
    )
    db.add(new_dispute)
    await db.commit()
    await db.refresh(new_dispute)
    
    return DisputeResponse(
        id=new_dispute.id,
        order_id=new_dispute.order_id,
        order_number=order.order_number,
        buyer_id=new_dispute.buyer_id,
        buyer_email=current_user.email,
        supplier_id=new_dispute.supplier_id,
        supplier_name="Supplier",
        status=new_dispute.status.value,
        reason=new_dispute.reason.value,
        buyer_description=new_dispute.buyer_description,
        created_at=new_dispute.created_at
    )

@router.get("/disputes", response_model=List[DisputeResponse])
async def list_disputes(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Dispute)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Dispute.buyer_id == current_user.id)
    if status:
        query = query.where(Dispute.status == status)
    
    query = query.order_by(desc(Dispute.created_at)).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    disputes = result.scalars().all()
    
    responses = []
    for d in disputes:
        o_res = await db.execute(select(Order.order_number).where(Order.id == d.order_id))
        order_number = o_res.scalar() or "Unknown"
        u_res = await db.execute(select(User.email).where(User.id == d.buyer_id))
        buyer_email = u_res.scalar() or "Unknown"

        responses.append(DisputeResponse(
            id=d.id,
            order_id=d.order_id,
            order_number=order_number,
            buyer_id=d.buyer_id,
            buyer_email=buyer_email,
            supplier_id=d.supplier_id,
            supplier_name="Supplier",
            status=d.status.value,
            reason=d.reason.value,
            buyer_description=d.buyer_description,
            created_at=d.created_at
        ))
    return responses

@router.post("/disputes/{dispute_id}/resolve")
async def resolve_dispute(
    dispute_id: str,
    resolution: str,
    refund_amount: float = 0.0,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Dispute).where(Dispute.id == dispute_id))
    dispute = result.scalar_one_or_none()
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    
    dispute.status = DisputeStatus.RESOLVED
    dispute.admin_resolution = resolution
    dispute.refund_amount = refund_amount
    dispute.assigned_to = admin.id
    dispute.resolved_at = datetime.utcnow()
    await db.commit()
    return {"message": "Dispute resolved"}

# === ANALYTICS ===

@router.get("/analytics/commission")
async def get_commission_analytics(
    supplier_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.commission_engine import CommissionEngine

    from datetime import timedelta
    period_start = datetime.utcnow() - timedelta(days=days)
    period_end = datetime.utcnow()

    if supplier_id:
        payout = await CommissionEngine.calculate_supplier_payout(
            supplier_id=supplier_id,
            period_start=period_start,
            period_end=period_end,
            db=db,
        )
        return payout

    suppliers_result = await db.execute(select(Supplier).limit(50))
    suppliers = suppliers_result.scalars().all()

    total_commission = 0.0
    total_sales = 0.0
    supplier_breakdown = []

    for s in suppliers:
        payout = await CommissionEngine.calculate_supplier_payout(
            supplier_id=s.id,
            period_start=period_start,
            period_end=period_end,
            db=db,
        )
        total_commission += payout["commission"]
        total_sales += payout["gross_sales"]
        supplier_breakdown.append(payout)

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "days": days,
        "total_sales": round(total_sales, 2),
        "total_commission": round(total_commission, 2),
        "effective_rate": round(total_commission / total_sales * 100, 2) if total_sales else 0,
        "suppliers_count": len(suppliers),
        "supplier_breakdown": supplier_breakdown[:20],
    }


@router.get("/analytics/orders")
async def get_order_analytics(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    data = []
    for i in range(days):
        date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        data.append({
            "date": date,
            "orders_count": 10 + i % 5,
            "orders_amount": 150000 + (i * 1000) % 50000,
            "commission": 7500 + (i * 50) % 2500
        })
    return data


# === RISK CHECKS & STOP LISTS ===

@router.post("/risk-check")
async def run_risk_check(
    inn: str = Query(..., min_length=10, max_length=12),
    company_name: str = "",
    email: str = "",
    phone: str = "",
    admin: User = Depends(require_admin),
):
    from app.services.risk_engine import CounterpartyRiskEngine
    result = await CounterpartyRiskEngine.check_supplier(
        inn=inn, company_name=company_name, email=email, phone=phone
    )
    return result.to_dict()


@router.get("/stop-list")
async def list_stop_list(admin: User = Depends(require_admin)):
    from app.services.risk_engine import StopListManager
    return {"entries": StopListManager.list_all()}


@router.post("/stop-list")
async def add_to_stop_list(
    inn: str = Query(..., min_length=10, max_length=12),
    reason: str = Query(..., min_length=2),
    admin: User = Depends(require_admin),
):
    from app.services.risk_engine import StopListManager
    StopListManager.add(inn=inn, reason=reason, added_by=admin.id)
    return {"message": "Added to stop list", "inn": inn}


@router.delete("/stop-list/{inn}")
async def remove_from_stop_list(
    inn: str,
    admin: User = Depends(require_admin),
):
    from app.services.risk_engine import StopListManager
    removed = StopListManager.remove(inn)
    if removed:
        return {"message": "Removed from stop list", "inn": inn}
    raise HTTPException(status_code=404, detail="INN not found in stop list")


# === SUBSCRIPTION MANAGEMENT ===

@router.get("/subscriptions/pricing")
async def get_subscription_pricing(admin: User = Depends(require_admin)):
    from app.services.subscription import SubscriptionService
    return SubscriptionService.get_pricing()


@router.get("/subscriptions/{user_id}")
async def get_user_subscription(
    user_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.subscription import SubscriptionService
    return await SubscriptionService.get_subscription_status(user_id, db)


# === PREMIUM PLACEMENT ===

@router.get("/premium/products")
async def list_premium_products(
    category_id: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.ranking_engine import RankingEngine
    return await RankingEngine.get_premium_products(category_id=category_id, limit=limit, db=db)


# === STO LEAD FEES ===

@router.get("/sto-lead-fees/{partner_id}")
async def get_sto_lead_fees(
    partner_id: str,
    days: int = Query(30, ge=1, le=365),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.ranking_engine import LeadFeeEngine
    from datetime import timedelta
    period_start = datetime.utcnow() - timedelta(days=days)
    return await LeadFeeEngine.get_partner_lead_fees(
        partner_id=partner_id, period_start=period_start, db=db
    )
