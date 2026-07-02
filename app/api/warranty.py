from datetime import datetime
from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_active_user
from app.core.database import get_db
from app.models.warranty import NotificationSettings, ServiceReminder, Warranty
from app.services.integration_service import integration_service

router = APIRouter(prefix="/warranty", tags=["Гарантия"])


class WarrantyResponse(BaseModel):
    id: str
    product_id: str
    order_id: str
    installation_id: str | None
    warranty_months: int
    warranty_km: int
    start_date: datetime
    end_date: datetime
    is_active: bool

    class Config:
        from_attributes = True


class ReminderResponse(BaseModel):
    id: str
    vehicle_id: str
    reminder_type: str
    due_date: datetime | None
    due_km: int | None
    is_sent: bool
    is_completed: bool
    title: str
    description: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ReminderCreate(BaseModel):
    vehicle_id: str
    reminder_type: str
    due_date: datetime | None = None
    due_km: int | None = None
    title: str
    description: str | None = None


class NotificationSettingsResponse(BaseModel):
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    telegram_enabled: bool
    telegram_chat_id: str | None
    order_updates: bool
    marketing: bool
    reminders: bool

    class Config:
        from_attributes = True


class NotificationSettingsUpdate(BaseModel):
    email_enabled: bool | None = None
    sms_enabled: bool | None = None
    push_enabled: bool | None = None
    telegram_enabled: bool | None = None
    telegram_chat_id: str | None = None
    order_updates: bool | None = None
    marketing: bool | None = None
    reminders: bool | None = None


@router.get("/warranties", response_model=List[WarrantyResponse])
async def get_warranties(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(
        select(Warranty)
        .where(Warranty.user_id == current_user.id, Warranty.is_active == True)
        .order_by(Warranty.end_date.desc())
    )
    return result.scalars().all()


@router.get("/warranties/{warranty_id}", response_model=WarrantyResponse)
async def get_warranty(
    warranty_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(
        select(Warranty).where(Warranty.id == warranty_id, Warranty.user_id == current_user.id)
    )
    warranty = result.scalar_one_or_none()
    if not warranty:
        raise HTTPException(status_code=404, detail="Гарантия не найдена")
    return warranty


@router.get("/reminders", response_model=List[ReminderResponse])
async def get_reminders(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(
        select(ServiceReminder)
        .where(ServiceReminder.user_id == current_user.id, ServiceReminder.is_completed == False)
        .order_by(ServiceReminder.due_date.asc())
    )
    return result.scalars().all()


@router.post("/reminders", response_model=ReminderResponse)
async def create_reminder(
    data: ReminderCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    reminder = ServiceReminder(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        vehicle_id=data.vehicle_id,
        reminder_type=data.reminder_type,
        due_date=data.due_date,
        due_km=data.due_km,
        title=data.title,
        description=data.description,
    )
    db.add(reminder)
    await db.commit()
    await db.refresh(reminder)

    settings_result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == current_user.id)
    )
    settings = settings_result.scalar_one_or_none()
    integration_service.notify_with_preferences(
        email=current_user.email,
        phone=current_user.phone,
        telegram_chat_id=settings.telegram_chat_id if settings else None,
        email_enabled=settings.email_enabled if settings else True,
        sms_enabled=settings.sms_enabled if settings else False,
        telegram_enabled=settings.telegram_enabled if settings else False,
        message=f"Создано напоминание: {reminder.title}",
    )

    return reminder


@router.post("/reminders/{reminder_id}/complete")
async def complete_reminder(
    reminder_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(
        select(ServiceReminder).where(
            ServiceReminder.id == reminder_id,
            ServiceReminder.user_id == current_user.id,
        )
    )
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Напоминание не найдено")

    reminder.is_completed = True
    reminder.completed_at = datetime.utcnow()
    await db.commit()
    return {"status": "ok"}


@router.get("/notifications/settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = NotificationSettings(id=str(uuid.uuid4()), user_id=current_user.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return settings


@router.put("/notifications/settings", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    data: NotificationSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    result = await db.execute(
        select(NotificationSettings).where(NotificationSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = NotificationSettings(id=str(uuid.uuid4()), user_id=current_user.id)
        db.add(settings)

    for key, value in data.model_dump(exclude_none=True).items():
        setattr(settings, key, value)

    await db.commit()
    await db.refresh(settings)
    return settings


@router.post("/notifications/test-push")
async def test_push_notification(current_user=Depends(get_current_active_user)):
    result = integration_service.send_notification(
        channel="telegram",
        to=current_user.email,
        message="Тестовое уведомление TruckHub",
    )
    return {
        "status": "ok",
        "message": "Тестовое уведомление отправлено",
        "provider_result": result,
    }