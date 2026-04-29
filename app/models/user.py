from sqlalchemy import Column, String, Boolean, DateTime, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
from app.core.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole, values_callable=lambda enum_cls: [item.value for item in enum_cls], native_enum=False), default=UserRole.BUYER.value, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    company_name = Column(String, nullable=True)
    inn = Column(String, nullable=True)
    address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    orders = relationship("Order", back_populates="user")
    supplier_profile = relationship("Supplier", uselist=False)
    vehicles = relationship("Vehicle", back_populates="user")
    cart = relationship("Cart", back_populates="user", uselist=False)


