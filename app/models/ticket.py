"""Support ticket system for manager workflow.

Ticket lifecycle: open -> in_progress -> waiting_buyer -> waiting_supplier -> resolved -> closed
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class TicketStatus:
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_BUYER = "waiting_buyer"
    WAITING_SUPPLIER = "waiting_supplier"
    RESOLVED = "resolved"
    CLOSED = "closed"

    ALL = [OPEN, IN_PROGRESS, WAITING_BUYER, WAITING_SUPPLIER, RESOLVED, CLOSED]
    ACTIVE = [OPEN, IN_PROGRESS, WAITING_BUYER, WAITING_SUPPLIER]


class TicketPriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    ALL = [LOW, MEDIUM, HIGH, CRITICAL]


class TicketCategory:
    ORDER = "order"
    DELIVERY = "delivery"
    PAYMENT = "payment"
    RETURN = "return"
    WARRANTY = "warranty"
    QUALITY = "quality"
    ACCOUNT = "account"
    OTHER = "other"

    ALL = [ORDER, DELIVERY, PAYMENT, RETURN, WARRANTY, QUALITY, ACCOUNT, OTHER]


class Ticket(Base):
    __tablename__ = "support_tickets"

    id = Column(String, primary_key=True, index=True)
    ticket_number = Column(String, unique=True, index=True, nullable=False)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String, default=TicketCategory.OTHER)
    priority = Column(String, default=TicketPriority.MEDIUM)
    status = Column(String, default=TicketStatus.OPEN)

    creator_id = Column(String, ForeignKey("users.id"), nullable=False)
    assignee_id = Column(String, ForeignKey("users.id"), nullable=True)

    order_id = Column(String, ForeignKey("orders.id"), nullable=True)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=True)

    sla_deadline = Column(DateTime, nullable=True)
    first_response_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    comments = relationship("TicketComment", back_populates="ticket", cascade="all, delete-orphan")


class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id = Column(String, primary_key=True, index=True)
    ticket_id = Column(String, ForeignKey("support_tickets.id"), nullable=False)
    author_id = Column(String, ForeignKey("users.id"), nullable=False)

    content = Column(Text, nullable=False)
    is_internal = Column(Integer, default=0)  # 0=public, 1=internal (manager-only)

    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="comments")
