from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from app.core.database import get_db
from app.models.user import User
from app.models.service import ServicePartner, ServiceSlot, InstallationBooking, ServiceReview
from app.schemas.service import (
    ServicePartnerCreate, ServicePartnerResponse,
    ServiceSlotResponse, BookingCreate, BookingResponse, BookingListResponse,
    ReviewCreate, ReviewResponse
)
from app.api.auth import get_current_active_user
from app.core.rbac import require_roles
from app.core.enums import UserRole
from app.core.messages import Msg

router = APIRouter(prefix="/service", tags=["Сервис"])

ALLOWED_BOOKING_STATUSES = {"pending", "confirmed", "in_progress", "completed", "cancelled"}
BOOKING_STATUS_TRANSITIONS = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"in_progress", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


def _normalize_booking_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized not in ALLOWED_BOOKING_STATUSES:
        raise HTTPException(status_code=422, detail=Msg.INVALID_BOOKING_STATUS)
    return normalized


def _can_transition_booking_status(current: str, target: str) -> bool:
    current_norm = (current or "").strip().lower()
    target_norm = (target or "").strip().lower()
    if current_norm == target_norm:
        return True
    return target_norm in BOOKING_STATUS_TRANSITIONS.get(current_norm, set())


# === PARTNERS ===

@router.get("/partners", response_model=List[ServicePartnerResponse])
async def list_partners(
    city: Optional[str] = None,
    service_type: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(ServicePartner).where(ServicePartner.is_active == True)

    if city:
        query = query.where(ServicePartner.city.ilike(f"%{city}%"))

    if service_type:
        query = query.where(ServicePartner.services.ilike(f"%{service_type}%"))

    query = query.order_by(desc(ServicePartner.rating)).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/partners/{partner_id}", response_model=ServicePartnerResponse)
async def get_partner(partner_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ServicePartner).where(ServicePartner.id == partner_id))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail=Msg.PARTNER_NOT_FOUND)
    return partner


@router.get("/partners/{partner_id}/rating-summary")
async def get_partner_rating_summary(
    partner_id: str,
    db: AsyncSession = Depends(get_db)
):
    partner_result = await db.execute(select(ServicePartner).where(ServicePartner.id == partner_id))
    partner = partner_result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail=Msg.PARTNER_NOT_FOUND)

    agg_result = await db.execute(
        select(func.avg(ServiceReview.rating), func.count(ServiceReview.id))
        .where(ServiceReview.partner_id == partner_id)
    )
    avg_rating, reviews_count = agg_result.one()

    recent_result = await db.execute(
        select(ServiceReview)
        .where(ServiceReview.partner_id == partner_id)
        .order_by(desc(ServiceReview.created_at))
        .limit(5)
    )
    recent_reviews = recent_result.scalars().all()

    return {
        "partner_id": partner_id,
        "rating": float(avg_rating) if avg_rating else 0.0,
        "reviews_count": int(reviews_count or 0),
        "recent_reviews": [
            {
                "id": r.id,
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recent_reviews
        ],
    }


@router.get("/partners/{partner_id}/slots", response_model=List[ServiceSlotResponse])
async def get_partner_slots(
    partner_id: str,
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    from_date = datetime.fromisoformat(date_from)
    to_date = datetime.fromisoformat(date_to)

    result = await db.execute(
        select(ServiceSlot)
        .where(
            ServiceSlot.partner_id == partner_id,
            ServiceSlot.date >= from_date,
            ServiceSlot.date <= to_date,
            ServiceSlot.is_booked == False
        )
        .order_by(ServiceSlot.date, ServiceSlot.start_time)
    )
    return result.scalars().all()


@router.post("/partners/{partner_id}/slots/generate")
async def generate_slots(
    partner_id: str,
    start_date: str,
    days: int = 7,
    start_hour: int = 9,
    end_hour: int = 18,
    slot_duration: int = 60,
    admin: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ServicePartner).where(ServicePartner.id == partner_id))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail=Msg.PARTNER_NOT_FOUND)

    start = datetime.fromisoformat(start_date)
    slots_created = 0

    for day in range(days):
        current_date = start + timedelta(days=day)
        for hour in range(start_hour, end_hour):
            for minute in [0, slot_duration]:
                if minute >= 60:
                    continue
                slot_time = current_date.replace(hour=hour, minute=minute)
                end_time = f"{hour}:{minute + slot_duration:02d}" if minute + slot_duration < 60 else f"{hour + 1}:00"

                exists_result = await db.execute(
                    select(ServiceSlot).where(
                        ServiceSlot.partner_id == partner_id,
                        ServiceSlot.date == slot_time,
                        ServiceSlot.start_time == f"{hour}:{minute:02d}",
                    )
                )
                if exists_result.scalar_one_or_none():
                    continue

                slot = ServiceSlot(
                    id=str(uuid.uuid4()),
                    partner_id=partner_id,
                    date=slot_time,
                    start_time=f"{hour}:{minute:02d}",
                    end_time=end_time,
                )
                db.add(slot)
                slots_created += 1

    await db.commit()
    return {"message": Msg.slots_created(slots_created)}


# === BOOKINGS ===

@router.post("/bookings", response_model=BookingResponse)
async def create_booking(
    booking: BookingCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    slot_result = await db.execute(select(ServiceSlot).where(ServiceSlot.id == booking.slot_id))
    slot = slot_result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail=Msg.SLOT_NOT_FOUND)
    if slot.is_booked:
        raise HTTPException(status_code=400, detail=Msg.SLOT_ALREADY_BOOKED)

    partner_result = await db.execute(select(ServicePartner).where(ServicePartner.id == booking.partner_id))
    partner = partner_result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail=Msg.PARTNER_NOT_FOUND)

    booking_id = str(uuid.uuid4())

    new_booking = InstallationBooking(
        id=booking_id,
        partner_id=booking.partner_id,
        customer_name=booking.customer_name,
        customer_phone=booking.customer_phone,
        customer_email=booking.customer_email,
        vehicle_vin=booking.vehicle_vin,
        vehicle_model=booking.vehicle_model,
        service_type=booking.service_type,
        product_name=booking.product_name,
        slot_id=booking.slot_id,
        appointment_date=slot.date,
        price=booking.price,
        notes=booking.notes,
        status="pending",
    )
    db.add(new_booking)

    slot.is_booked = True
    slot.booking_id = booking_id

    await db.commit()
    await db.refresh(new_booking)

    return BookingResponse(
        id=new_booking.id,
        partner_id=partner.id,
        partner_name=partner.company_name,
        customer_name=new_booking.customer_name,
        customer_phone=new_booking.customer_phone,
        vehicle_vin=new_booking.vehicle_vin,
        vehicle_model=new_booking.vehicle_model,
        service_type=new_booking.service_type,
        product_name=new_booking.product_name,
        appointment_date=new_booking.appointment_date,
        price=new_booking.price,
        status=new_booking.status,
        created_at=new_booking.created_at
    )


@router.get("/bookings/my")
async def list_my_bookings(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(InstallationBooking).where(InstallationBooking.customer_email == current_user.email)

    if status:
        query = query.where(InstallationBooking.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    query = query.order_by(desc(InstallationBooking.created_at)).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    bookings = result.scalars().all()

    booking_responses = []
    for b in bookings:
        partner_result = await db.execute(select(ServicePartner).where(ServicePartner.id == b.partner_id))
        partner = partner_result.scalar_one_or_none()
        booking_responses.append({
            "id": b.id,
            "partner_id": b.partner_id,
            "partner_name": partner.company_name if partner else "Unknown",
            "partner_address": partner.address if partner else "",
            "partner_phone": partner.phone if partner else "",
            "customer_name": b.customer_name,
            "customer_phone": b.customer_phone,
            "vehicle_vin": b.vehicle_vin,
            "vehicle_model": b.vehicle_model,
            "service_type": b.service_type,
            "product_name": b.product_name,
            "appointment_date": b.appointment_date.isoformat() if b.appointment_date else None,
            "price": b.price,
            "status": b.status,
            "notes": b.notes,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })

    return {"bookings": booking_responses, "total": total}


@router.get("/bookings", response_model=BookingListResponse)
async def list_bookings(
    partner_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(UserRole.SERVICE, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    query = select(InstallationBooking)

    if partner_id:
        query = query.where(InstallationBooking.partner_id == partner_id)
    if status:
        query = query.where(InstallationBooking.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    query = query.order_by(desc(InstallationBooking.created_at)).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    bookings = result.scalars().all()

    booking_responses = []
    for b in bookings:
        partner_result = await db.execute(select(ServicePartner).where(ServicePartner.id == b.partner_id))
        partner = partner_result.scalar_one_or_none()
        booking_responses.append(BookingResponse(
            id=b.id,
            partner_id=b.partner_id,
            partner_name=partner.company_name if partner else "Unknown",
            customer_name=b.customer_name,
            customer_phone=b.customer_phone,
            vehicle_vin=b.vehicle_vin,
            vehicle_model=b.vehicle_model,
            service_type=b.service_type,
            product_name=b.product_name,
            appointment_date=b.appointment_date,
            price=b.price,
            status=b.status,
            created_at=b.created_at
        ))

    return BookingListResponse(bookings=booking_responses, total=total)


@router.put("/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: str,
    status: str,
    current_user: User = Depends(require_roles(UserRole.SERVICE, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(InstallationBooking).where(InstallationBooking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail=Msg.BOOKING_NOT_FOUND)

    target_status = _normalize_booking_status(status)
    if not _can_transition_booking_status(booking.status, target_status):
        raise HTTPException(status_code=409, detail=Msg.INVALID_BOOKING_TRANSITION)

    booking.status = target_status

    if target_status == "cancelled":
        slot_result = await db.execute(select(ServiceSlot).where(ServiceSlot.id == booking.slot_id))
        slot = slot_result.scalar_one_or_none()
        if slot:
            slot.is_booked = False
            slot.booking_id = None

    await db.commit()
    return {"message": Msg.BOOKING_STATUS_UPDATED, "status": target_status}


# === REVIEWS ===

@router.post("/reviews", response_model=ReviewResponse)
async def create_review(
    review: ReviewCreate,
    current_user: User = Depends(require_roles(UserRole.SERVICE, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db)
):
    booking_result = await db.execute(select(InstallationBooking).where(InstallationBooking.id == review.booking_id))
    booking = booking_result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail=Msg.BOOKING_NOT_FOUND)

    new_review = ServiceReview(
        id=str(uuid.uuid4()),
        booking_id=review.booking_id,
        partner_id=booking.partner_id,
        user_id=current_user.id,
        rating=review.rating,
        comment=review.comment,
        photos=",".join(review.photos) if review.photos else None,
    )
    db.add(new_review)

    reviews_result = await db.execute(
        select(func.avg(ServiceReview.rating), func.count(ServiceReview.id))
        .where(ServiceReview.partner_id == booking.partner_id)
    )
    avg_rating, count = reviews_result.one()

    partner_result = await db.execute(select(ServicePartner).where(ServicePartner.id == booking.partner_id))
    partner = partner_result.scalar_one_or_none()
    if partner:
        partner.rating = float(avg_rating) if avg_rating else 0.0
        partner.reviews_count = count

    await db.commit()
    await db.refresh(new_review)

    return new_review


@router.get("/partners/{partner_id}/reviews")
async def get_partner_reviews(
    partner_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    query = select(ServiceReview).where(ServiceReview.partner_id == partner_id)
    query = query.order_by(desc(ServiceReview.created_at)).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    return result.scalars().all()
