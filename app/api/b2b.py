from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime, timedelta
import uuid

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.models.order import Order
from app.models.product import Product
from app.schemas.b2b import (
    CreditApplicationCreate,
    CreditApplicationResponse,
    PaymentDeferralRequest,
    PaymentDeferralResponse,
    QuoteRequestCreate,
    QuoteRequestResponse,
    QuoteRequestItem,
    PromocodeCreate,
    PromocodeResponse,
    ReferralProgramResponse,
)
from app.api.auth import get_current_active_user
from app.core.messages import Msg

router = APIRouter(prefix="/b2b", tags=["B2B"])


# in-memory demo storage for MVP B2B workflow
quote_requests_storage: list[dict] = []
promocodes_storage: list[dict] = []


# === CREDIT APPLICATIONS ===

@router.post("/credits", response_model=CreditApplicationResponse)
async def create_credit_application(
    data: CreditApplicationCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.inn:
        raise HTTPException(status_code=400, detail=Msg.INN_REQUIRED_CREDIT)

    application = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "amount": data.amount,
        "term_months": data.term_months,
        "purpose": data.purpose,
        "status": "pending",
        "created_at": datetime.utcnow(),
    }

    return CreditApplicationResponse(
        id=application["id"],
        user_id=application["user_id"],
        amount=application["amount"],
        term_months=application["term_months"],
        purpose=application["purpose"],
        status=application["status"],
        created_at=application["created_at"],
    )


@router.get("/credits", response_model=List[CreditApplicationResponse])
async def list_credit_applications(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return [
        CreditApplicationResponse(
            id="1",
            user_id=current_user.id,
            amount=500000,
            term_months=12,
            purpose="Закупка запчастей",
            status="approved",
            approved_amount=450000,
            interest_rate=18.5,
            monthly_payment=41250,
            created_at=datetime.utcnow() - timedelta(days=30),
        )
    ]


# === PAYMENT DEFERRAL ===

@router.post("/deferrals", response_model=PaymentDeferralResponse)
async def request_payment_deferral(
    data: PaymentDeferralRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.inn:
        raise HTTPException(status_code=400, detail=Msg.INN_REQUIRED_DEFERRAL)

    result = await db.execute(select(Order).where(Order.id == data.order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=Msg.ORDER_NOT_FOUND)

    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=Msg.NOT_YOUR_ORDER)

    deferral = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "order_id": data.order_id,
        "defer_days": data.defer_days,
        "status": "pending",
        "approved_until": datetime.utcnow() + timedelta(days=data.defer_days),
        "created_at": datetime.utcnow(),
    }

    return PaymentDeferralResponse(
        id=deferral["id"],
        user_id=deferral["user_id"],
        order_id=deferral["order_id"],
        defer_days=deferral["defer_days"],
        status=deferral["status"],
        approved_until=deferral["approved_until"],
        created_at=deferral["created_at"],
    )


# === B2B QUOTE REQUEST WORKFLOW ===

@router.post("/quotes", response_model=QuoteRequestResponse)
async def create_quote_request(
    data: QuoteRequestCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.inn:
        raise HTTPException(status_code=400, detail=Msg.INN_REQUIRED_QUOTE)

    if not data.items:
        raise HTTPException(status_code=422, detail=Msg.QUOTE_ITEMS_REQUIRED)

    normalized_items: List[QuoteRequestItem] = []
    for item in data.items:
        if item.quantity <= 0:
            raise HTTPException(status_code=422, detail=Msg.QUOTE_ITEM_QTY_POSITIVE)

        product_result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = product_result.scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=Msg.product_not_found_id(item.product_id))

        normalized_items.append(
            QuoteRequestItem(
                product_id=item.product_id,
                quantity=item.quantity,
                target_price=item.target_price,
            )
        )

    quote = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "title": data.title,
        "comment": data.comment,
        "status": "pending",
        "need_by_date": data.need_by_date,
        "items": [item.model_dump() for item in normalized_items],
        "total_items": len(normalized_items),
        "created_at": datetime.utcnow(),
    }
    quote_requests_storage.append(quote)

    return QuoteRequestResponse(
        id=quote["id"],
        user_id=quote["user_id"],
        title=quote["title"],
        comment=quote["comment"],
        status=quote["status"],
        need_by_date=quote["need_by_date"],
        items=[QuoteRequestItem(**i) for i in quote["items"]],
        total_items=quote["total_items"],
        created_at=quote["created_at"],
    )


@router.get("/quotes", response_model=List[QuoteRequestResponse])
async def list_quote_requests(
    current_user: User = Depends(get_current_active_user),
):
    user_quotes = [q for q in quote_requests_storage if q.get("user_id") == current_user.id]
    user_quotes.sort(key=lambda q: q["created_at"], reverse=True)

    return [
        QuoteRequestResponse(
            id=q["id"],
            user_id=q["user_id"],
            title=q["title"],
            comment=q.get("comment"),
            status=q["status"],
            need_by_date=q.get("need_by_date"),
            items=[QuoteRequestItem(**i) for i in q.get("items", [])],
            total_items=q.get("total_items", 0),
            created_at=q["created_at"],
        )
        for q in user_quotes
    ]


@router.get("/quotes/{quote_id}", response_model=QuoteRequestResponse)
async def get_quote_request(
    quote_id: str,
    current_user: User = Depends(get_current_active_user),
):
    quote = next((q for q in quote_requests_storage if q.get("id") == quote_id), None)
    if not quote:
        raise HTTPException(status_code=404, detail=Msg.QUOTE_NOT_FOUND)

    if quote.get("user_id") != current_user.id:
        raise HTTPException(status_code=403, detail=Msg.NOT_YOUR_QUOTE)

    return QuoteRequestResponse(
        id=quote["id"],
        user_id=quote["user_id"],
        title=quote["title"],
        comment=quote.get("comment"),
        status=quote["status"],
        need_by_date=quote.get("need_by_date"),
        items=[QuoteRequestItem(**i) for i in quote.get("items", [])],
        total_items=quote.get("total_items", 0),
        created_at=quote["created_at"],
    )


# === PROMOCODES ===

@router.post("/promocodes", response_model=PromocodeResponse)
async def create_promocode(
    data: PromocodeCreate,
    admin: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    promo = {
        "id": str(uuid.uuid4()),
        "code": data.code.upper(),
        "discount_type": data.discount_type,
        "discount_value": data.discount_value,
        "min_order_amount": data.min_order_amount,
        "max_uses": data.max_uses,
        "uses_count": 0,
        "is_active": True,
        "valid_from": data.valid_from,
        "valid_to": data.valid_to,
    }
    promocodes_storage.append(promo)

    return PromocodeResponse(**promo)


@router.post("/promocodes/validate")
async def validate_promocode(
    code: str,
    order_amount: float,
    db: AsyncSession = Depends(get_db),
):
    for promo in promocodes_storage:
        if promo["code"] == code.upper() and promo["is_active"]:
            if order_amount < (promo["min_order_amount"] or 0):
                return {"valid": False, "error": f"Минимальная сумма заказа: {promo['min_order_amount']} ₽"}

            if datetime.utcnow() < promo["valid_from"] or datetime.utcnow() > promo["valid_to"]:
                return {"valid": False, "error": "Промокод недействителен"}

            if promo["max_uses"] and promo["uses_count"] >= promo["max_uses"]:
                return {"valid": False, "error": "Промокод использован"}

            discount = promo["discount_value"]
            if promo["discount_type"] == "percent":
                discount = order_amount * (promo["discount_value"] / 100)

            return {
                "valid": True,
                "discount": discount,
                "discount_type": promo["discount_type"],
                "discount_value": promo["discount_value"],
            }

    return {"valid": False, "error": "Промокод не найден"}


@router.get("/promocodes", response_model=List[PromocodeResponse])
async def list_promocodes(
    admin: User = Depends(get_current_active_user),
):
    return promocodes_storage


# === REFERRAL PROGRAM ===

@router.get("/referral", response_model=ReferralProgramResponse)
async def get_referral_info(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return ReferralProgramResponse(
        referral_code=current_user.id[:8].upper(),
        referral_link=f"{settings.SITE_URL}/ref/{current_user.id[:8]}",
        referrals_count=15,
        earned_amount=25000,
        pending_amount=5000,
    )


@router.post("/referral/withdraw")
async def withdraw_referral_bonus(
    amount: float,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    return {"message": Msg.credit_request_submitted(amount)}
