from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
import enum


class WarehouseType(str, enum.Enum):
    OWN = "own"
    SUPPLIER = "supplier"
    CONSIGNATION = "consignation"


class WarehouseStock(Base):
    __tablename__ = "warehouse_stocks"

    id = Column(String, primary_key=True, index=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    
    warehouse_type = Column(String, default=WarehouseType.OWN.value)
    warehouse_id = Column(String, nullable=True)
    
    quantity_available = Column(Integer, default=0)
    quantity_reserved = Column(Integer, default=0)
    quantity_waiting = Column(Integer, default=0)
    
    last_sync_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
