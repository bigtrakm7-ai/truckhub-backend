from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, Float, Boolean, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    shipment_id = Column(String, ForeignKey("order_items.id"), nullable=True)
    
    buyer_id = Column(String, ForeignKey("users.id"), nullable=False)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False)
    
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    
    is_approved = Column(Boolean, default=False)
    is_visible = Column(Boolean, default=True)
    
    admin_reply = Column(Text, nullable=True)
    admin_reply_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
    )


class SupplierRating(Base):
    __tablename__ = "supplier_ratings"

    id = Column(String, primary_key=True, index=True)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False, unique=True)
    
    total_reviews = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)
    
    rating_5_count = Column(Integer, default=0)
    rating_4_count = Column(Integer, default=0)
    rating_3_count = Column(Integer, default=0)
    rating_2_count = Column(Integer, default=0)
    rating_1_count = Column(Integer, default=0)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
