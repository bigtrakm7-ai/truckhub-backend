from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
import enum


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=True)
    company_name = Column(String, nullable=False)
    inn = Column(String, unique=True, index=True, nullable=False)
    address = Column(String, nullable=True)
    warehouse_address = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    rating = Column(Float, default=0.0)
    balance = Column(Float, default=0.0)
    commission_rate = Column(Float, default=0.05)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    products = relationship("Product", back_populates="supplier")


class PriceFormat(str, enum.Enum):
    CSV = "csv"
    XLS = "xls"
    XLSX = "xlsx"
    XML = "xml"
    YML = "yml"


class PriceUpload(Base):
    __tablename__ = "price_uploads"

    id = Column(String, primary_key=True, index=True)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False)

    filename = Column(String, nullable=False)
    format = Column(SQLEnum(PriceFormat), nullable=False)
    import_kind = Column(String, default="products")

    total_products = Column(Integer, default=0)
    updated_products = Column(Integer, default=0)
    new_products = Column(Integer, default=0)
    errors = Column(Integer, default=0)

    status = Column(String, default="pending")
    error_log = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class SupplierBalance(Base):
    __tablename__ = "supplier_balances"

    id = Column(String, primary_key=True, index=True)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False)

    amount = Column(Float, nullable=False)
    transaction_type = Column(String, nullable=False)
    description = Column(String, nullable=True)

    balance_before = Column(Float, nullable=False)
    balance_after = Column(Float, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)


class SupplierAnalytics(Base):
    __tablename__ = "supplier_analytics"

    id = Column(String, primary_key=True, index=True)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False)

    product_id = Column(String, ForeignKey("products.id"), nullable=True)

    views_count = Column(Integer, default=0)
    cart_adds = Column(Integer, default=0)
    orders_count = Column(Integer, default=0)
    conversion_rate = Column(Float, default=0.0)

    date = Column(DateTime, default=datetime.utcnow)

