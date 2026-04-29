from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base
import enum


class VehicleType(str, enum.Enum):
    TRUCK = "truck"
    SEMITRAILER = "semitrailer"
    BUS = "bus"


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    vin = Column(String, unique=True, index=True, nullable=False)
    reg_number = Column(String, nullable=True)
    
    vehicle_type = Column(SQLEnum(VehicleType), default=VehicleType.TRUCK)
    
    brand = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=True)
    
    engine = Column(String, nullable=True)
    chassis = Column(String, nullable=True)
    
    mileage = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)
    
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="vehicles")
