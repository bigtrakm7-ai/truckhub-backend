from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
import enum


class DisputeStatus(str, enum.Enum):
    OPEN = "open"
    NEGOTIATION = "negotiation"
    ESCALATED = "escalated"
    ARBITRATION = "arbitration"
    RESOLVED = "resolved"
    CLOSED = "closed"


class DisputeReason(str, enum.Enum):
    NOT_AS_DESCRIBED = "not_as_described"
    DEFECTIVE = "defective"
    WRONG_ITEM = "wrong_item"
    LATE_DELIVERY = "late_delivery"
    QUALITY_ISSUE = "quality_issue"
    MISSING_PARTS = "missing_parts"
    WARRANTY_CLAIM = "warranty_claim"
    OTHER = "other"


class DisputeResolution(str, enum.Enum):
    FULL_REFUND = "full_refund"
    PARTIAL_REFUND = "partial_refund"
    REPLACEMENT = "replacement"
    REPAIR = "repair"
    REJECTED = "rejected"
    MUTUAL_AGREEMENT = "mutual_agreement"


class BannerPosition(str, enum.Enum):
    HOME_TOP = "home_top"
    HOME_MIDDLE = "home_middle"
    HOME_BOTTOM = "home_bottom"
    CATALOG_TOP = "catalog_top"
    PRODUCT_PAGE = "product_page"


class Banner(Base):
    __tablename__ = "banners"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    subtitle = Column(String, nullable=True)
    image_url = Column(String, nullable=False)
    link_url = Column(String, nullable=True)
    
    position = Column(SQLEnum(BannerPosition), default=BannerPosition.HOME_TOP)
    
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    
    clicks_count = Column(Integer, default=0)
    views_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommissionRule(Base):
    __tablename__ = "commission_rules"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    
    category_id = Column(String, nullable=True)
    supplier_id = Column(String, nullable=True)
    
    commission_percent = Column(Float, nullable=False)
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, nullable=False)
    order_item_id = Column(String, nullable=True)
    
    buyer_id = Column(String, nullable=False)
    supplier_id = Column(String, nullable=False)
    
    status = Column(SQLEnum(DisputeStatus), default=DisputeStatus.OPEN)
    reason = Column(SQLEnum(DisputeReason), nullable=False)
    resolution_type = Column(SQLEnum(DisputeResolution), nullable=True)
    
    buyer_description = Column(Text, nullable=False)
    supplier_response = Column(Text, nullable=True)
    admin_resolution = Column(Text, nullable=True)
    
    refund_amount = Column(Float, default=0.0)
    
    assigned_to = Column(String, nullable=True)

    # SLA fields
    sla_response_deadline = Column(DateTime, nullable=True)
    sla_resolution_deadline = Column(DateTime, nullable=True)
    buyer_responded_at = Column(DateTime, nullable=True)
    supplier_responded_at = Column(DateTime, nullable=True)
    escalation_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class UserVerification(Base):
    __tablename__ = "user_verifications"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=False)
    
    user_type = Column(String, nullable=False)
    
    documents = Column(Text, nullable=True)
    
    status = Column(String, default="pending")
    verified_by = Column(String, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(String, primary_key=True, index=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id = Column(String, nullable=True)
    
    user_id = Column(String, nullable=True)
    admin_id = Column(String, nullable=True)
    
    details = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
