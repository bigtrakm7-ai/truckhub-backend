from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from app.core.database import Base


class Warranty(Base):
    __tablename__ = "warranties"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    
    installation_id = Column(String, ForeignKey("installation_bookings.id"), nullable=True)
    
    warranty_months = Column(Integer, default=12)
    warranty_km = Column(Integer, default=100000)
    
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=False)
    
    is_active = Column(Boolean, default=True)
    terms_text = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ServiceReminder(Base):
    __tablename__ = "service_reminders"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=False)
    
    reminder_type = Column(String, nullable=False)
    
    due_date = Column(DateTime, nullable=True)
    due_km = Column(Integer, nullable=True)
    
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class NotificationSettings(Base):
    __tablename__ = "notification_settings"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    
    email_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=True)
    push_enabled = Column(Boolean, default=True)
    telegram_enabled = Column(Boolean, default=False)
    
    telegram_chat_id = Column(String, nullable=True)
    
    order_updates = Column(Boolean, default=True)
    marketing = Column(Boolean, default=False)
    reminders = Column(Boolean, default=True)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WarrantyClaimStatus:
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_REPAIR = "in_repair"
    REPLACED = "replaced"
    REFUNDED = "refunded"
    CLOSED = "closed"


class WarrantyClaim(Base):
    __tablename__ = "warranty_claims"

    id = Column(String, primary_key=True, index=True)
    claim_number = Column(String, unique=True, index=True, nullable=False)
    warranty_id = Column(String, ForeignKey("warranties.id"), nullable=False)
    
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    supplier_id = Column(String, nullable=True)
    
    status = Column(String, default=WarrantyClaimStatus.SUBMITTED)
    
    defect_description = Column(Text, nullable=False)
    defect_photos = Column(Text, nullable=True)
    requested_resolution = Column(String, nullable=True)
    
    supplier_response = Column(Text, nullable=True)
    admin_decision = Column(Text, nullable=True)
    resolution_type = Column(String, nullable=True)
    refund_amount = Column(Integer, nullable=True)
    
    reviewed_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
