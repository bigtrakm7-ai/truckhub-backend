"""Support ticket API — manager + buyer/supplier self-service."""

from datetime import datetime, timedelta
from typing import Optional, List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_active_user
from app.core.database import get_db
from app.core.enums import UserRole
from app.core.rbac import require_roles
from app.models.ticket import Ticket, TicketComment, TicketStatus, TicketPriority, TicketCategory
from app.models.user import User
from pydantic import BaseModel
from app.core.messages import Msg

router = APIRouter(prefix="/support", tags=["Поддержка"])

# ── SLA config ───────────────────────────────────────────────────────

SLA_HOURS = {
    TicketPriority.CRITICAL: 2,
    TicketPriority.HIGH: 4,
    TicketPriority.MEDIUM: 8,
    TicketPriority.LOW: 24,
}


# ── Schemas ──────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    title: str
    description: str
    category: str = TicketCategory.OTHER
    priority: str = TicketPriority.MEDIUM
    order_id: Optional[str] = None


class CommentCreate(BaseModel):
    content: str
    is_internal: bool = False


class TicketAssign(BaseModel):
    assignee_id: str


class TicketStatusUpdate(BaseModel):
    status: str
    priority: Optional[str] = None


# ── Manager endpoints ────────────────────────────────────────────────

@router.get("/dashboard")
async def manager_dashboard(
    current_user: User = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    open_count = await db.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.status.in_(TicketStatus.ACTIVE))
    ) or 0
    unassigned = await db.scalar(
        select(func.count()).select_from(Ticket).where(
            Ticket.status.in_(TicketStatus.ACTIVE), Ticket.assignee_id == None
        )
    ) or 0
    my_open = await db.scalar(
        select(func.count()).select_from(Ticket).where(
            Ticket.assignee_id == current_user.id, Ticket.status.in_(TicketStatus.ACTIVE)
        )
    ) or 0

    overdue = await db.scalar(
        select(func.count()).select_from(Ticket).where(
            Ticket.sla_deadline < datetime.utcnow(),
            Ticket.status.in_(TicketStatus.ACTIVE),
        )
    ) or 0

    resolved_today = await db.scalar(
        select(func.count()).select_from(Ticket).where(
            Ticket.resolved_at >= datetime.utcnow().replace(hour=0, minute=0, second=0),
        )
    ) or 0

    by_priority = {}
    for p in TicketPriority.ALL:
        cnt = await db.scalar(
            select(func.count()).select_from(Ticket).where(
                Ticket.priority == p, Ticket.status.in_(TicketStatus.ACTIVE)
            )
        ) or 0
        if cnt > 0:
            by_priority[p] = cnt

    by_category = {}
    for c in TicketCategory.ALL:
        cnt = await db.scalar(
            select(func.count()).select_from(Ticket).where(
                Ticket.category == c, Ticket.status.in_(TicketStatus.ACTIVE)
            )
        ) or 0
        if cnt > 0:
            by_category[c] = cnt

    return {
        "open_count": open_count,
        "unassigned_count": unassigned,
        "my_open_count": my_open,
        "overdue_count": overdue,
        "resolved_today": resolved_today,
        "by_priority": by_priority,
        "by_category": by_category,
    }


@router.get("/tickets")
async def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    assignee_id: Optional[str] = None,
    unassigned: bool = False,
    overdue: bool = False,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    query = select(Ticket)

    if status and status in TicketStatus.ALL:
        query = query.where(Ticket.status == status)
    elif not status:
        query = query.where(Ticket.status.in_(TicketStatus.ACTIVE))

    if priority and priority in TicketPriority.ALL:
        query = query.where(Ticket.priority == priority)
    if category and category in TicketCategory.ALL:
        query = query.where(Ticket.category == category)
    if assignee_id:
        query = query.where(Ticket.assignee_id == assignee_id)
    if unassigned:
        query = query.where(Ticket.assignee_id == None)
    if overdue:
        query = query.where(Ticket.sla_deadline < datetime.utcnow(), Ticket.status.in_(TicketStatus.ACTIVE))

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0

    query = query.order_by(Ticket.priority.desc(), Ticket.created_at.asc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    tickets = result.scalars().all()

    return {
        "tickets": [
            {
                "id": t.id,
                "ticket_number": t.ticket_number,
                "title": t.title,
                "category": t.category,
                "priority": t.priority,
                "status": t.status,
                "creator_id": t.creator_id,
                "assignee_id": t.assignee_id,
                "order_id": t.order_id,
                "sla_deadline": t.sla_deadline.isoformat() if t.sla_deadline else None,
                "is_overdue": t.sla_deadline and t.sla_deadline < datetime.utcnow() and t.status in TicketStatus.ACTIVE,
                "first_response_at": t.first_response_at.isoformat() if t.first_response_at else None,
                "comments_count": 0,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in tickets
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    current_user: User = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail=Msg.TICKET_NOT_FOUND)

    comments_result = await db.execute(
        select(TicketComment).where(TicketComment.ticket_id == ticket_id)
        .order_by(TicketComment.created_at.asc())
    )
    comments = comments_result.scalars().all()

    creator_result = await db.execute(select(User).where(User.id == ticket.creator_id))
    creator = creator_result.scalar_one_or_none()

    assignee = None
    if ticket.assignee_id:
        assignee_result = await db.execute(select(User).where(User.id == ticket.assignee_id))
        a = assignee_result.scalar_one_or_none()
        if a:
            assignee = {"id": a.id, "email": a.email, "name": a.company_name or a.email}

    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "creator": {"id": creator.id, "email": creator.email, "name": creator.company_name or creator.email} if creator else None,
        "assignee": assignee,
        "order_id": ticket.order_id,
        "sla_deadline": ticket.sla_deadline.isoformat() if ticket.sla_deadline else None,
        "is_overdue": ticket.sla_deadline and ticket.sla_deadline < datetime.utcnow() and ticket.status in TicketStatus.ACTIVE,
        "first_response_at": ticket.first_response_at.isoformat() if ticket.first_response_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "comments": [
            {
                "id": c.id,
                "author_id": c.author_id,
                "content": c.content,
                "is_internal": bool(c.is_internal),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in comments
        ],
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
    }


@router.put("/tickets/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: str,
    data: TicketAssign,
    current_user: User = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail=Msg.TICKET_NOT_FOUND)

    assignee_result = await db.execute(select(User).where(User.id == data.assignee_id))
    assignee = assignee_result.scalar_one_or_none()
    if not assignee or assignee.role not in (UserRole.MANAGER, UserRole.ADMIN):
        raise HTTPException(status_code=400, detail=Msg.ASSIGNEE_MUST_BE_MANAGER)

    ticket.assignee_id = data.assignee_id
    if ticket.status == TicketStatus.OPEN:
        ticket.status = TicketStatus.IN_PROGRESS
        if not ticket.first_response_at:
            ticket.first_response_at = datetime.utcnow()

    await db.commit()
    return {"id": ticket.id, "status": ticket.status, "assignee_id": ticket.assignee_id}


@router.put("/tickets/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: str,
    data: TicketStatusUpdate,
    current_user: User = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail=Msg.TICKET_NOT_FOUND)

    if data.status not in TicketStatus.ALL:
        raise HTTPException(status_code=400, detail=Msg.invalid_status_valid(", ".join(TicketStatus.ALL)))

    ticket.status = data.status
    if data.priority and data.priority in TicketPriority.ALL:
        ticket.priority = data.priority

    if data.status == TicketStatus.RESOLVED:
        ticket.resolved_at = datetime.utcnow()
    elif data.status in TicketStatus.ACTIVE and ticket.resolved_at:
        ticket.resolved_at = None

    if ticket.status in (TicketStatus.IN_PROGRESS, TicketStatus.WAITING_BUYER, TicketStatus.WAITING_SUPPLIER):
        if not ticket.first_response_at:
            ticket.first_response_at = datetime.utcnow()

    await db.commit()
    return {"id": ticket.id, "status": ticket.status, "priority": ticket.priority}


@router.post("/tickets/{ticket_id}/comments")
async def add_comment(
    ticket_id: str,
    data: CommentCreate,
    current_user: User = Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail=Msg.TICKET_NOT_FOUND)

    comment = TicketComment(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        author_id=current_user.id,
        content=data.content,
        is_internal=1 if data.is_internal else 0,
    )
    db.add(comment)

    if not ticket.first_response_at and not data.is_internal:
        ticket.first_response_at = datetime.utcnow()
        if ticket.status == TicketStatus.OPEN:
            ticket.status = TicketStatus.IN_PROGRESS

    ticket.updated_at = datetime.utcnow()
    await db.commit()

    return {
        "id": comment.id,
        "ticket_id": comment.ticket_id,
        "author_id": comment.author_id,
        "content": comment.content,
        "is_internal": comment.is_internal,
        "created_at": comment.created_at.isoformat(),
    }


# ── Buyer/Supplier self-service ──────────────────────────────────────

@router.post("/tickets")
async def create_ticket(
    data: TicketCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if data.category not in TicketCategory.ALL:
        raise HTTPException(status_code=400, detail=Msg.invalid_category_valid(", ".join(TicketCategory.ALL)))
    if data.priority not in TicketPriority.ALL:
        raise HTTPException(status_code=400, detail=Msg.invalid_priority_valid(", ".join(TicketPriority.ALL)))

    ticket_id = str(uuid.uuid4())
    ticket_number = f"TH-{datetime.now().strftime('%Y%m%d')}-{ticket_id[:6].upper()}"

    sla_hours = SLA_HOURS.get(data.priority, 8)
    sla_deadline = datetime.utcnow() + timedelta(hours=sla_hours)

    ticket = Ticket(
        id=ticket_id,
        ticket_number=ticket_number,
        title=data.title,
        description=data.description,
        category=data.category,
        priority=data.priority,
        status=TicketStatus.OPEN,
        creator_id=current_user.id,
        order_id=data.order_id,
        sla_deadline=sla_deadline,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "status": ticket.status,
        "sla_deadline": ticket.sla_deadline.isoformat(),
    }


@router.get("/my-tickets")
async def list_my_tickets(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Ticket).where(Ticket.creator_id == current_user.id)

    if status and status in TicketStatus.ALL:
        query = query.where(Ticket.status == status)

    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0

    query = query.order_by(Ticket.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    tickets = result.scalars().all()

    return {
        "tickets": [
            {
                "id": t.id,
                "ticket_number": t.ticket_number,
                "title": t.title,
                "category": t.category,
                "priority": t.priority,
                "status": t.status,
                "assignee_id": t.assignee_id,
                "sla_deadline": t.sla_deadline.isoformat() if t.sla_deadline else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ],
        "total": total,
    }


@router.get("/my-tickets/{ticket_id}")
async def get_my_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.creator_id == current_user.id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail=Msg.TICKET_NOT_FOUND)

    comments_result = await db.execute(
        select(TicketComment).where(
            TicketComment.ticket_id == ticket_id,
            TicketComment.is_internal == 0,
        ).order_by(TicketComment.created_at.asc())
    )
    comments = comments_result.scalars().all()

    return {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "order_id": ticket.order_id,
        "sla_deadline": ticket.sla_deadline.isoformat() if ticket.sla_deadline else None,
        "comments": [
            {
                "id": c.id,
                "author_id": c.author_id,
                "content": c.content,
                "is_internal": False,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in comments
        ],
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
    }


@router.post("/my-tickets/{ticket_id}/comments")
async def add_my_comment(
    ticket_id: str,
    data: CommentCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.creator_id == current_user.id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail=Msg.TICKET_NOT_FOUND)

    if ticket.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
        raise HTTPException(status_code=400, detail=Msg.TICKET_ALREADY_CLOSED)

    comment = TicketComment(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        author_id=current_user.id,
        content=data.content,
        is_internal=0,
    )
    db.add(comment)

    if ticket.status == TicketStatus.WAITING_BUYER:
        ticket.status = TicketStatus.IN_PROGRESS
    ticket.updated_at = datetime.utcnow()
    await db.commit()

    return {"id": comment.id, "content": comment.content, "created_at": comment.created_at.isoformat()}
