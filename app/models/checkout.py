from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
import enum


class DeliveryMethod(str, enum.Enum):
    COURIER = "courier"
    SDEK = "sdek"
    DELOVYE_LINII = "delovye_linii"
    PEK = "pek"
    PICKUP = "pickup"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    PACKED = "packed"
    SHIPPED = "shipped"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentMethod(str, enum.Enum):
    CARD_ONLINE = "card_online"
    SBP = "sbp"
    INVOICE = "invoice"
    INSTALLMENT = "installment"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class DeliveryRequest(Base):
    __tablename__ = "delivery_requests"

    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    
    method = Column(SQLEnum(DeliveryMethod), nullable=False)
    
    address_from = Column(String, nullable=True)
    address_to = Column(String, nullable=False)
    
    weight = Column(Float, nullable=True)
    dimensions = Column(String, nullable=True)
    
    estimated_days = Column(Integer, nullable=True)
    price = Column(Float, nullable=False)
    
    tracking_number = Column(String, nullable=True)
    status = Column(SQLEnum(DeliveryStatus), default=DeliveryStatus.PENDING)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Cart(Base):
    __tablename__ = "carts"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    session_id = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="cart")
    items = relationship("CartItem", back_populates="cart")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(String, primary_key=True, index=True)
    cart_id = Column(String, ForeignKey("carts.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    
    quantity = Column(Integer, nullable=False, default=1)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")


class CartResponse(Base):
    __tablename__ = "cart_responses"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    items = Column(Text, nullable=True)
    total_amount = Column(Float, default=0.0)
    items_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
