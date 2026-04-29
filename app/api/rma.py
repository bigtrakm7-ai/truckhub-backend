from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from datetime import datetime
import uuid

from app.core.database import get_db
from app.models.user import User
from app.models.order import Order, OrderItem
from app.models.supplier import Supplier
from app.models.rma import ReturnRequest
from app.models.warranty import NotificationSettings
from app.schemas.rma import (
    ReturnRequestCreate, ReturnRequestResponse, ReturnRequestListResponse,
    ReturnStatusUpdate, ReturnTrackingUpdate
)
from app.api.auth import get_current_active_user
from app.services import integration_service

router = APIRouter(prefix="/returns", tags=["Returns (RMA)"])


@router.post("/", response_model=ReturnRequestResponse)
async def create_return_request(
    request_data: ReturnRequestCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    order_result = await db.execute(select(Order).where(Order.id == request_data.order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your order")
    
    refund_amount = 0.0
    supplier_id = None
    
    if request_data.order_item_id:
        item_result = await db.execute(
            select(OrderItem).where(
                OrderItem.id == request_data.order_item_id,
                OrderItem.order_id == request_data.order_id
            )
        )
        item = item_result.scalar_one_or_none()
        if item:
            refund_amount = item.unit_price * request_data.quantity
            supplier_id = item.supplier_id
    else:
        refund_amount = order.total_amount * request_data.quantity / max(order.total_amount, 1)
    
    photos = ",".join(request_data.photos) if request_data.photos else None
    
    return_request = ReturnRequest(
        id=str(uuid.uuid4()),
        order_id=request_data.order_id,
        order_item_id=request_data.order_item_id,
        user_id=current_user.id,
        supplier_id=supplier_id,
        reason=request_data.reason,
        description=request_data.description,
        quantity=request_data.quantity,
        refund_amount=refund_amount,
        photos=photos,
    )
    db.add(return_request)
    await db.commit()
    await db.refresh(return_request)
    
    return ReturnRequestResponse(
        id=return_request.id,
        order_id=return_request.order_id,
        order_item_id=return_request.order_item_id,
        order_number=order.order_number,
        user_id=return_request.user_id,
        user_email=current_user.email,
        supplier_id=return_request.supplier_id,
        supplier_name=None,
        status=return_request.status.value,
        reason=return_request.reason.value,
        description=return_request.description,
        quantity=return_request.quantity,
        refund_amount=return_request.refund_amount,
        photos=request_data.photos,
        admin_notes=None,
        resolution=None,
        tracking_number=None,
        created_at=return_request.created_at,
        inspected_at=None,
        refunded_at=None
    )


@router.get("/", response_model=ReturnRequestListResponse)
async def list_return_requests(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(ReturnRequest).where(ReturnRequest.user_id == current_user.id)
    
    if status:
        query = query.where(ReturnRequest.status == status)
    
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    query = query.order_by(desc(ReturnRequest.created_at)).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    requests = result.scalars().all()
    
    responses = []
    for r in requests:
        order_result = await db.execute(select(Order).where(Order.id == r.order_id))
        order = order_result.scalar_one_or_none()
        
        supplier_name = None
        if r.supplier_id:
            sup_result = await db.execute(select(Supplier).where(Supplier.id == r.supplier_id))
            sup = sup_result.scalar_one_or_none()
            if sup:
                supplier_name = sup.company_name
        
        photos = r.photos.split(",") if r.photos else None
        
        responses.append(ReturnRequestResponse(
            id=r.id,
            order_id=r.order_id,
            order_item_id=r.order_item_id,
            order_number=order.order_number if order else "Unknown",
            user_id=r.user_id,
            user_email=current_user.email,
            supplier_id=r.supplier_id,
            supplier_name=supplier_name,
            status=r.status.value,
            reason=r.reason.value,
            description=r.description,
            quantity=r.quantity,
            refund_amount=r.refund_amount,
            photos=photos,
            admin_notes=r.admin_notes,
            resolution=r.resolution,
            tracking_number=r.tracking_number,
            created_at=r.created_at,
            inspected_at=r.inspected_at,
            refunded_at=r.refunded_at
        ))
    
    return ReturnRequestListResponse(requests=responses, total=total)


@router.get("/{return_id}", response_model=ReturnRequestResponse)
async def get_return_request(
    return_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ReturnRequest).where(ReturnRequest.id == return_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Return request not found")
    
    if r.user_id != current_user.id and current_user.role.value not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    order_result = await db.execute(select(Order).where(Order.id == r.order_id))
    order = order_result.scalar_one_or_none()
    
    supplier_name = None
    if r.supplier_id:
        sup_result = await db.execute(select(Supplier).where(Supplier.id == r.supplier_id))
        sup = sup_result.scalar_one_or_none()
        if sup:
            supplier_name = sup.company_name
    
    photos = r.photos.split(",") if r.photos else None
    
    return ReturnRequestResponse(
        id=r.id,
        order_id=r.order_id,
        order_item_id=r.order_item_id,
        order_number=order.order_number if order else "Unknown",
        user_id=r.user_id,
        user_email=current_user.email,
        supplier_id=r.supplier_id,
        supplier_name=supplier_name,
        status=r.status.value,
        reason=r.reason.value,
        description=r.description,
        quantity=r.quantity,
        refund_amount=r.refund_amount,
        photos=photos,
        admin_notes=r.admin_notes,
        resolution=r.resolution,
        tracking_number=r.tracking_number,
        created_at=r.created_at,
        inspected_at=r.inspected_at,
        refunded_at=r.refunded_at
    )


@router.put("/{return_id}/status")
async def update_return_status(
    return_id: str,
    status_update: ReturnStatusUpdate,
    admin: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ReturnRequest).where(ReturnRequest.id == return_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Return request not found")
    
    r.status = status_update.status
    if status_update.admin_notes:
        r.admin_notes = status_update.admin_notes
    if status_update.resolution:
        r.resolution = status_update.resolution
    if status_update.refund_amount:
        r.refund_amount = status_update.refund_amount
    
    if status_update.status == "inspected":
        r.inspected_at = datetime.utcnow()
    elif status_update.status == "refunded":
        r.refunded_at = datetime.utcnow()
    
    await db.commit()

    # P0-2: notify return status change
    user_result = await db.execute(select(User).where(User.id == r.user_id))
    req_user = user_result.scalar_one_or_none()
    notification_settings_result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == r.user_id)
    )
    notification_settings = notification_settings_result.scalar_one_or_none()
    integration_service.notify_with_preferences(
        email=req_user.email if req_user else None,
        phone=req_user.phone if req_user else None,
        telegram_chat_id=notification_settings.telegram_chat_id if notification_settings else None,
        email_enabled=notification_settings.email_enabled if notification_settings else True,
        sms_enabled=notification_settings.sms_enabled if notification_settings else False,
        telegram_enabled=notification_settings.telegram_enabled if notification_settings else False,
        message=f"Return {r.id}: status changed to {r.status.value}",
    )
    return {"message": "Return status updated"}


@router.put("/{return_id}/tracking")
async def update_return_tracking(
    return_id: str,
    tracking: ReturnTrackingUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ReturnRequest).where(ReturnRequest.id == return_id))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Return request not found")
    
    r.tracking_number = tracking.tracking_number
    await db.commit()
    return {"message": "Tracking number updated"}


