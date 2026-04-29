from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
import enum


class ReturnReason(str, enum.Enum):
    NOT_NEEDED = "not_needed"
    WRONG_ITEM = "wrong_item"
    DEFECTIVE = "defective"
    NOT_AS_DESCRIBED = "not_as_described"
    LATE_DELIVERY = "late_delivery"
    OTHER = "other"


class ReturnStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RECEIVED = "received"
    INSPECTING = "inspecting"
    REFUND_PROCESSING = "refund_processing"
    REFUNDED = "refunded"
    CLOSED = "closed"


class ReturnRequest(Base):
    __tablename__ = "return_requests"

    id = Column(String, primary_key=True, index=True)
    
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    order_item_id = Column(String, ForeignKey("order_items.id"), nullable=True)
    
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=True)
    
    status = Column(SQLEnum(ReturnStatus), default=ReturnStatus.PENDING)
    reason = Column(SQLEnum(ReturnReason), nullable=False)
    
    description = Column(Text, nullable=True)
    
    quantity = Column(Integer, default=1)
    refund_amount = Column(Float, default=0.0)
    
    photos = Column(Text, nullable=True)
    
    admin_id = Column(String, ForeignKey("users.id"), nullable=True)
    admin_notes = Column(Text, nullable=True)
    resolution = Column(Text, nullable=True)
    
    tracking_number = Column(String, nullable=True)
    
    inspected_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
