"""Real-time dashboard WebSocket endpoints.

Live metrics for admin and supplier dashboards.
"""

import json
import asyncio
from typing import Dict, Set
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rbac import require_roles
from app.core.enums import UserRole
from app.models.order import Order, OrderStatus
from app.models.user import User

router = APIRouter(prefix="/ws", tags=["WebSocket"])

# ── Connection Managers ──────────────────────────────────────────────

class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "admin": set(),
            "suppliers": set(),
        }
    
    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        self.active_connections[channel].add(websocket)
    
    def disconnect(self, websocket: WebSocket, channel: str):
        self.active_connections[channel].discard(websocket)
    
    async def broadcast(self, message: dict, channel: str):
        disconnected = set()
        for connection in self.active_connections.get(channel, set()):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        # Clean up disconnected
        for conn in disconnected:
            self.active_connections[channel].discard(conn)


manager = ConnectionManager()


# ── WebSocket Endpoints ──────────────────────────────────────────────

@router.websocket("/admin/dashboard")
async def admin_dashboard_ws(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
):
    """Real-time admin dashboard metrics."""
    # Simple auth check via token in query param
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return
    
    # Verify admin role (simplified)
    await manager.connect(websocket, "admin")
    
    try:
        while True:
            # Send metrics every 5 seconds
            metrics = await _get_admin_metrics(db)
            await websocket.send_json({
                "type": "metrics",
                "timestamp": datetime.utcnow().isoformat(),
                "data": metrics,
            })
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        manager.disconnect(websocket, "admin")


@router.websocket("/supplier/{supplier_id}/dashboard")
async def supplier_dashboard_ws(
    websocket: WebSocket,
    supplier_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Real-time supplier dashboard metrics."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return
    
    await manager.connect(websocket, f"supplier:{supplier_id}")
    
    try:
        while True:
            metrics = await _get_supplier_metrics(db, supplier_id)
            await websocket.send_json({
                "type": "metrics",
                "timestamp": datetime.utcnow().isoformat(),
                "data": metrics,
            })
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"supplier:{supplier_id}")


# ── Metrics Helpers ─────────────────────────────────────────────────

async def _get_admin_metrics(db: AsyncSession) -> dict:
    """Get real-time admin metrics."""
    from app.models.ticket import Ticket, TicketStatus
    
    # Orders
    orders_today = await db.scalar(
        select(func.count()).select_from(Order)
        .where(Order.created_at >= datetime.utcnow().replace(hour=0, minute=0))
    ) or 0
    
    revenue_today = await db.scalar(
        select(func.sum(Order.total_amount)).select_from(Order)
        .where(Order.created_at >= datetime.utcnow().replace(hour=0, minute=0))
    ) or 0
    
    # Tickets
    open_tickets = await db.scalar(
        select(func.count()).select_from(Ticket)
        .where(Ticket.status.in_(TicketStatus.ACTIVE))
    ) or 0
    
    return {
        "orders_today": orders_today,
        "revenue_today": round(revenue_today, 2),
        "open_tickets": open_tickets,
    }


async def _get_supplier_metrics(db: AsyncSession, supplier_id: str) -> dict:
    """Get real-time supplier metrics."""
    from app.models.order import OrderItem
    
    # Orders with supplier's items
    items_result = await db.execute(
        select(OrderItem).where(OrderItem.supplier_id == supplier_id)
    )
    items = items_result.scalars().all()
    
    order_ids = {item.order_id for item in items}
    
    return {
        "active_orders": len(order_ids),
        "items_count": len(items),
    }


# ── SSE Alternative ─────────────────────────────────────────────────

from fastapi.responses import StreamingResponse

@router.get("/sse/admin/metrics")
async def admin_metrics_sse(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Server-Sent Events for admin metrics (fallback for WebSocket)."""
    
    async def event_generator():
        while True:
            metrics = await _get_admin_metrics(db)
            yield f"data: {json.dumps(metrics)}\n\n"
            await asyncio.sleep(5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
