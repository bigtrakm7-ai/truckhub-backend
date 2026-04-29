from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id = Column(String, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=True)
    
    buyer_id = Column(String, ForeignKey("users.id"), nullable=False)
    supplier_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    last_message = Column(Text, nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    
    buyer_unread = Column(Integer, default=0)
    supplier_unread = Column(Integer, default=0)
    
    is_buyer_blocked = Column(Boolean, default=False)
    is_supplier_blocked = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("chat_conversations.id"), nullable=False)
    
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    content = Column(Text, nullable=False)
    
    is_system = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    conversation = relationship("ChatConversation", back_populates="messages")


ChatConversation.messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")
