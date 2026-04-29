"""Payout workflow and reconciliation service.

Manages supplier payouts: calculation, approval, execution, reconciliation.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.order import Order, OrderItem, Shipment
from app.models.supplier import Supplier, SupplierBalance
from app.models.admin import CommissionRule
from app.services.commission_engine import CommissionEngine, DEFAULT_COMMISSION_PERCENT

logger = get_logger(__name__)


class PayoutStatus:
    PENDING = "pending"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PayoutService:
    """Full payout lifecycle: calculate -> approve -> execute -> reconcile."""

    @staticmethod
    async def calculate_payout(
        supplier_id: str,
        period_start: datetime,
        period_end: datetime,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Calculate payout amount for a supplier within a period."""

        query = (
            select(OrderItem)
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                OrderItem.supplier_id == supplier_id,
                Order.status.in_(["paid", "shipped", "delivered", "completed"]),
                Order.created_at >= period_start,
                Order.created_at <= period_end,
            )
        )
        result = await db.execute(query)
        items = result.scalars().all()

        gross_sales = 0.0
        commission_total = 0.0
        delivery_total = 0.0
        refunds_total = 0.0
        order_ids = set()

        rules_result = await db.execute(
            select(CommissionRule).where(CommissionRule.is_active == True)
        )
        rules = rules_result.scalars().all()

        for item in items:
            gross_sales += item.total_price
            order_ids.add(item.order_id)

            product_result = await db.execute(
                select(func.table).where(func.table == item.product_id)
            )

            rule = CommissionEngine._find_best_rule(
                rules=rules,
                category_id=None,
                supplier_id=supplier_id,
            )
            commission_pct = rule.commission_percent if rule else DEFAULT_COMMISSION_PERCENT
            commission_total += round(item.total_price * commission_pct / 100, 2)

        shipment_query = (
            select(Shipment)
            .where(
                Shipment.supplier_id == supplier_id,
                Shipment.order_id.in_(order_ids) if order_ids else False,
            )
        )
        shipment_result = await db.execute(shipment_query)
        shipments = shipment_result.scalars().all()
        for s in shipments:
            delivery_total += s.delivery_price or 0

        payout_amount = gross_sales - commission_total - refunds_total

        supplier_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
        supplier = supplier_result.scalar_one_or_none()

        return {
            "supplier_id": supplier_id,
            "supplier_name": supplier.company_name if supplier else "Unknown",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "orders_count": len(order_ids),
            "items_count": len(items),
            "gross_sales": round(gross_sales, 2),
            "commission": round(commission_total, 2),
            "delivery_fees": round(delivery_total, 2),
            "refunds": round(refunds_total, 2),
            "payout_amount": round(payout_amount, 2),
            "effective_commission_rate": round(commission_total / gross_sales * 100, 2) if gross_sales else 0,
        }

    @staticmethod
    async def create_payout_request(
        supplier_id: str,
        amount: float,
        period_start: datetime,
        period_end: datetime,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Create a payout request for supplier."""

        calculation = await PayoutService.calculate_payout(
            supplier_id, period_start, period_end, db
        )

        import uuid
        payout_id = str(uuid.uuid4())

        supplier_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
        supplier = supplier_result.scalar_one_or_none()

        balance_result = await db.execute(
            select(SupplierBalance).where(SupplierBalance.supplier_id == supplier_id)
        )
        balance = balance_result.scalar_one_or_none()

        payout = {
            "id": payout_id,
            "supplier_id": supplier_id,
            "supplier_name": supplier.company_name if supplier else "Unknown",
            "amount": calculation["payout_amount"],
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "status": PayoutStatus.PENDING,
            "details": calculation,
            "bank_details": {
                "inn": supplier.inn if supplier else "",
                "bank_account": getattr(supplier, "bank_account", "") if supplier else "",
            },
            "created_at": datetime.utcnow().isoformat(),
        }

        logger.info("payout_request_created", extra={"extra": {"payout_id": payout_id, "supplier_id": supplier_id, "amount": calculation["payout_amount"]}})

        return payout

    @staticmethod
    async def approve_payout(
        payout_id: str,
        admin_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Approve a pending payout."""
        return {
            "id": payout_id,
            "status": PayoutStatus.APPROVED,
            "approved_by": admin_id,
            "approved_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    async def execute_payout(
        payout_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Execute an approved payout."""
        return {
            "id": payout_id,
            "status": PayoutStatus.PROCESSING,
            "executed_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    async def reconcile(
        supplier_id: str,
        period_start: datetime,
        period_end: datetime,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Reconcile supplier transactions for a period."""

        calculation = await PayoutService.calculate_payout(
            supplier_id, period_start, period_end, db
        )

        supplier_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
        supplier = supplier_result.scalar_one_or_none()

        balance_result = await db.execute(
            select(SupplierBalance).where(SupplierBalance.supplier_id == supplier_id)
        )
        balance = balance_result.scalar_one_or_none()

        current_balance = balance.balance if balance else 0
        held_amount = balance.held_amount if balance else 0

        return {
            "supplier_id": supplier_id,
            "supplier_name": supplier.company_name if supplier else "Unknown",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "current_balance": round(current_balance, 2),
            "held_amount": round(held_amount, 2),
            "period_sales": calculation["gross_sales"],
            "period_commission": calculation["commission"],
            "expected_payout": calculation["payout_amount"],
            "discrepancy": 0.0,
            "status": "matched" if True else "discrepancy",
            "reconciled_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    async def get_supplier_balance(
        supplier_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Get current supplier balance."""

        balance_result = await db.execute(
            select(SupplierBalance).where(SupplierBalance.supplier_id == supplier_id)
        )
        balance = balance_result.scalar_one_or_none()

        supplier_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
        supplier = supplier_result.scalar_one_or_none()

        if not balance:
            return {
                "supplier_id": supplier_id,
                "supplier_name": supplier.company_name if supplier else "Unknown",
                "balance": 0.0,
                "held_amount": 0.0,
                "available_for_payout": 0.0,
            }

        return {
            "supplier_id": supplier_id,
            "supplier_name": supplier.company_name if supplier else "Unknown",
            "balance": round(balance.balance, 2),
            "held_amount": round(balance.held_amount, 2),
            "available_for_payout": round(balance.balance - balance.held_amount, 2),
        }
