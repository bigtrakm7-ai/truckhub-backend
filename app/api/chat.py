from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime
import uuid

from app.core.database import get_db
from app.api.auth import get_current_active_user
from app.models.chat import ChatConversation, ChatMessage
from app.models.user import User
from app.core.messages import Msg

router = APIRouter(prefix="/chat", tags=["Чат"])


class MessageCreate(BaseModel):
    conversation_id: str
    content: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    content: str
    is_system: bool
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: str
    order_id: str | None
    buyer_id: str
    supplier_id: str
    last_message: str | None
    last_message_at: datetime | None
    buyer_unread: int
    supplier_unread: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    order_id: str | None = None
    supplier_id: str


@router.get("/conversations", response_model=List[ConversationResponse])
def get_conversations(db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    conversations = db.query(ChatConversation).filter(
        (ChatConversation.buyer_id == current_user.id) |
        (ChatConversation.supplier_id == current_user.id)
    ).order_by(ChatConversation.last_message_at.desc()).all()
    return conversations


@router.get("/conversations/{conversation_id}", response_model=List[MessageResponse])
def get_messages(conversation_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        (ChatConversation.buyer_id == current_user.id) |
        (ChatConversation.supplier_id == current_user.id)
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail=Msg.CONVERSATION_NOT_FOUND)
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).order_by(ChatMessage.created_at.asc()).all()
    
    for msg in messages:
        if msg.sender_id != current_user.id and not msg.is_read:
            msg.is_read = True
    db.commit()
    
    return messages


@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(data: ConversationCreate, db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    existing = db.query(ChatConversation).filter(
        ChatConversation.supplier_id == data.supplier_id,
        ChatConversation.buyer_id == current_user.id
    ).first()
    
    if existing:
        return existing
    
    conversation = ChatConversation(
        id=str(uuid.uuid4()),
        buyer_id=current_user.id,
        supplier_id=data.supplier_id,
        order_id=data.order_id
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.post("/messages", response_model=MessageResponse)
def send_message(data: MessageCreate, db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    from app.services.chat_moderation import moderate_message

    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == data.conversation_id,
        (ChatConversation.buyer_id == current_user.id) |
        (ChatConversation.supplier_id == current_user.id)
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail=Msg.CONVERSATION_NOT_FOUND)

    moderation = moderate_message(data.content)
    content_to_save = moderation.sanitized_content if not moderation.is_clean else data.content
    
    message = ChatMessage(
        id=str(uuid.uuid4()),
        conversation_id=data.conversation_id,
        sender_id=current_user.id,
        content=content_to_save
    )

    if not moderation.is_clean:
        message.is_flagged = True
    
    conversation.last_message = content_to_save[:100]
    conversation.last_message_at = datetime.utcnow()
    
    if current_user.id == conversation.buyer_id:
        conversation.supplier_unread += 1
    else:
        conversation.buyer_unread += 1
    
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.post("/conversations/{conversation_id}/block")
def block_conversation(conversation_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_active_user)):
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail=Msg.CONVERSATION_NOT_FOUND)
    
    if current_user.id == conversation.buyer_id:
        conversation.is_buyer_blocked = True
    elif current_user.id == conversation.supplier_id:
        conversation.is_supplier_blocked = True
    else:
        raise HTTPException(status_code=403, detail=Msg.ACCESS_DENIED)
    
    db.commit()
    return {"status": "ok"}
