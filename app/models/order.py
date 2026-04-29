from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
from app.core.enums import OrderStatus


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, index=True)
    order_number = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.DRAFT)
    
    total_amount = Column(Float, default=0.0)
    delivery_amount = Column(Float, default=0.0)
    commission_amount = Column(Float, default=0.0)
    
    delivery_address = Column(String, nullable=True)
    delivery_method = Column(String, nullable=True)
    tracking_number = Column(String, nullable=True)
    payment_method = Column(String, nullable=True)
    payment_status = Column(String, default="pending")
    payment_url = Column(String, nullable=True)
    buyer_name = Column(String, nullable=True)
    buyer_phone = Column(String, nullable=True)
    recipient_name = Column(String, nullable=True)
    recipient_phone = Column(String, nullable=True)
    
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")
    shipments = relationship("Shipment", back_populates="order", cascade="all, delete-orphan")


class ShipmentStatus:
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ASSEMBLING = "assembling"
    SHIPPED = "shipped"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=True)
    supplier_name = Column(String, nullable=True)
    
    status = Column(String, default=ShipmentStatus.PENDING)
    tracking_number = Column(String, nullable=True)
    delivery_provider = Column(String, nullable=True)
    delivery_price = Column(Float, default=0.0)
    delivery_days_min = Column(Integer, nullable=True)
    delivery_days_max = Column(Integer, nullable=True)
    
    weight_kg = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    
    shipped_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("Order", back_populates="shipments")
    items = relationship("OrderItem", back_populates="shipment")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=True)
    supplier_name = Column(String, nullable=True)
    shipment_id = Column(String, ForeignKey("shipments.id"), nullable=True)
    shipment_status = Column(String, default="pending")
    shipment_tracking_number = Column(String, nullable=True)
    
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    
    is_installation = Column(Boolean, default=False)
    installation_date = Column(DateTime, nullable=True)
    service_center_id = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    shipment = relationship("Shipment", back_populates="items")
