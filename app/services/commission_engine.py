"""Commission engine — applies commission rules to orders.

Rules are evaluated in priority order:
1. Supplier-specific rule (highest priority)
2. Category-specific rule
3. Default platform rule
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.admin import CommissionRule
from app.models.product import Product, Category
from app.models.order import Order, OrderItem
from app.models.supplier import Supplier

logger = get_logger(__name__)

DEFAULT_COMMISSION_PERCENT = 5.0
PREMIUM_PLACEMENT_FEE_PERCENT = 2.0
INSTALLATION_LEAD_FEE_PERCENT = 3.0


class CommissionEngine:
    """Calculate commissions for orders based on configurable rules."""

    @staticmethod
    async def calculate_order_commission(
        order: Order,
        items: List[OrderItem],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Calculate total commission for an order, broken down by item."""

        rules_result = await db.execute(
            select(CommissionRule).where(CommissionRule.is_active == True)
        )
        rules = rules_result.scalars().all()

        total_commission = 0.0
        item_commissions = []
        supplier_commissions: Dict[str, float] = {}

        for item in items:
            product_result = await db.execute(select(Product).where(Product.id == item.product_id))
            product = product_result.scalar_one_or_none()

            category_id = product.category_id if product else None
            supplier_id = item.supplier_id

            rule = CommissionEngine._find_best_rule(
                rules=rules,
                category_id=category_id,
                supplier_id=supplier_id,
            )

            commission_pct = rule.commission_percent if rule else DEFAULT_COMMISSION_PERCENT
            commission_amount = round(item.total_price * commission_pct / 100, 2)

            if product and getattr(product, "is_premium", False):
                premium_fee = round(item.total_price * PREMIUM_PLACEMENT_FEE_PERCENT / 100, 2)
                commission_amount += premium_fee

            if item.is_installation:
                lead_fee = round(item.total_price * INSTALLATION_LEAD_FEE_PERCENT / 100, 2)
                commission_amount += lead_fee

            total_commission += commission_amount

            if supplier_id:
                supplier_commissions[supplier_id] = supplier_commissions.get(supplier_id, 0) + commission_amount

            item_commissions.append({
                "item_id": item.id,
                "product_id": item.product_id,
                "supplier_id": supplier_id,
                "total_price": item.total_price,
                "commission_pct": commission_pct,
                "commission_amount": commission_amount,
                "is_premium": getattr(product, "is_premium", False) if product else False,
                "is_installation": item.is_installation,
            })

        order.commission_amount = total_commission

        return {
            "order_id": order.id,
            "total_amount": order.total_amount,
            "total_commission": round(total_commission, 2),
            "effective_rate": round(total_commission / order.total_amount * 100, 2) if order.total_amount else 0,
            "supplier_breakdown": [
                {"supplier_id": sid, "commission": round(amt, 2)}
                for sid, amt in supplier_commissions.items()
            ],
            "item_details": item_commissions,
        }

    @staticmethod
    def _find_best_rule(
        rules: List[CommissionRule],
        category_id: Optional[str] = None,
        supplier_id: Optional[str] = None,
    ) -> Optional[CommissionRule]:
        """Find the most specific matching commission rule.

        Priority: supplier+category > supplier > category > default
        """
        supplier_category_match = None
        supplier_match = None
        category_match = None
        default_match = None

        for rule in rules:
            if rule.supplier_id and rule.category_id:
                if rule.supplier_id == supplier_id and rule.category_id == category_id:
                    supplier_category_match = rule
            elif rule.supplier_id and not rule.category_id:
                if rule.supplier_id == supplier_id:
                    supplier_match = rule
            elif rule.category_id and not rule.supplier_id:
                if rule.category_id == category_id:
                    category_match = rule
            else:
                if not default_match:
                    default_match = rule

        return supplier_category_match or supplier_match or category_match or default_match

    @staticmethod
    async def calculate_supplier_payout(
        supplier_id: str,
        period_start=None,
        period_end=None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """Calculate payout for a supplier within a period."""

        query = select(OrderItem).where(OrderItem.supplier_id == supplier_id)
        if period_start:
            query = query.join(Order).where(Order.created_at >= period_start)
        if period_end:
            query = query.join(Order).where(Order.created_at <= period_end)

        result = await db.execute(query)
        items = result.scalars().all()

        gross_sales = sum(i.total_price for i in items)
        commission = gross_sales * DEFAULT_COMMISSION_PERCENT / 100

        supplier_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
        supplier = supplier_result.scalar_one_or_none()

        return {
            "supplier_id": supplier_id,
            "supplier_name": supplier.company_name if supplier else "Unknown",
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "gross_sales": round(gross_sales, 2),
            "commission": round(commission, 2),
            "payout_amount": round(gross_sales - commission, 2),
            "items_count": len(items),
        }
