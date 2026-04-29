from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, time
from app.core.database import Base
import enum


class ServicePartner(Base):
    __tablename__ = "service_partners"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    
    company_name = Column(String, nullable=False)
    inn = Column(String, unique=True, index=True, nullable=False)
    
    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    phone = Column(String, nullable=False)
    email = Column(String, nullable=True)
    
    rating = Column(Float, default=0.0)
    reviews_count = Column(Integer, default=0)
    
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    services = Column(Text, nullable=True)
    working_hours = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ServiceSlot(Base):
    __tablename__ = "service_slots"

    id = Column(String, primary_key=True, index=True)
    partner_id = Column(String, ForeignKey("service_partners.id"), nullable=False)
    
    date = Column(DateTime, nullable=False)
    start_time = Column(String, nullable=False)
    end_time = Column(String, nullable=False)
    
    is_booked = Column(Boolean, default=False)
    booking_id = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class InstallationBooking(Base):
    __tablename__ = "installation_bookings"

    id = Column(String, primary_key=True, index=True)
    
    order_id = Column(String, ForeignKey("orders.id"), nullable=True)
    order_item_id = Column(String, nullable=True)
    
    partner_id = Column(String, ForeignKey("service_partners.id"), nullable=False)
    
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    customer_email = Column(String, nullable=True)
    
    vehicle_vin = Column(String, nullable=True)
    vehicle_model = Column(String, nullable=True)
    
    service_type = Column(String, nullable=False)
    product_name = Column(String, nullable=True)
    
    slot_id = Column(String, ForeignKey("service_slots.id"), nullable=False)
    appointment_date = Column(DateTime, nullable=False)
    
    price = Column(Float, nullable=False)
    status = Column(String, default="pending")
    
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ServiceReview(Base):
    __tablename__ = "service_reviews"

    id = Column(String, primary_key=True, index=True)
    booking_id = Column(String, ForeignKey("installation_bookings.id"), nullable=False)
    partner_id = Column(String, ForeignKey("service_partners.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    
    photos = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
