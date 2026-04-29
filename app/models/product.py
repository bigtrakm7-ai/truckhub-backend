from sqlalchemy import Column, String, Text, Float, Integer, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
import enum


class ProductType(str, enum.Enum):
    ORIGINAL = "original"
    ANALOG = "analog"


class StockStatus(str, enum.Enum):
    IN_STOCK = "in_stock"
    ON_ORDER = "on_order"
    OUT_OF_STOCK = "out_of_stock"


class Category(Base):
    __tablename__ = "categories"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True)
    parent_id = Column(String, ForeignKey("categories.id"), nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    products = relationship("Product", back_populates="category")
    children = relationship("Category")


class Brand(Base):
    __tablename__ = "brands"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True)
    logo_url = Column(String, nullable=True)
    country = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    products = relationship("Product", back_populates="brand")


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)
    article = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category_id = Column(String, ForeignKey("categories.id"), nullable=True)
    brand_id = Column(String, ForeignKey("brands.id"), nullable=True)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=True)
    
    price = Column(Float, nullable=False)
    old_price = Column(Float, nullable=True)
    
    stock_quantity = Column(Integer, default=0)
    stock_status = Column(SQLEnum(StockStatus), default=StockStatus.OUT_OF_STOCK)
    
    weight = Column(Float, nullable=True)
    dimensions = Column(String, nullable=True)
    
    product_type = Column(SQLEnum(ProductType), default=ProductType.ORIGINAL)
    is_premium = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    images = Column(String, nullable=True)
    applicability = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("Category", back_populates="products")
    brand = relationship("Brand", back_populates="products")
    supplier = relationship("Supplier", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")
