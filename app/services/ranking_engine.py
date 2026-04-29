"""Premium placement and search ranking engine.

Products with is_premium=True get boosted in search results.
Ranking formula: base_score * premium_multiplier + relevance_score

Also handles STO lead-fee accounting for service partner referrals.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.product import Product
from app.models.service import ServicePartner

logger = get_logger(__name__)

# ── Premium Ranking ──────────────────────────────────────────────────

PREMIUM_BOOST = 1.5
IN_STOCK_BOOST = 1.2
VERIFIED_SUPPLIER_BOOST = 1.1
RATING_BOOST_FACTOR = 0.05  # per 0.1 rating above 4.0


class RankingEngine:
    """Calculate search ranking scores for products."""

    @staticmethod
    def calculate_score(
        product: Dict[str, Any],
        relevance_score: float = 1.0,
    ) -> float:
        """Calculate composite ranking score for a product."""
        score = relevance_score

        # Premium boost
        if product.get("is_premium"):
            score *= PREMIUM_BOOST

        # In-stock boost
        stock_qty = product.get("stock_quantity", 0)
        if stock_qty > 0:
            score *= IN_STOCK_BOOST

        # Verified supplier boost
        if product.get("supplier_verified"):
            score *= VERIFIED_SUPPLIER_BOOST

        # Rating boost
        rating = product.get("supplier_rating", 0)
        if rating > 4.0:
            score += (rating - 4.0) * RATING_BOOST_FACTOR * 10

        # Price competitiveness (lower price = slight boost within same relevance)
        price = product.get("price", 0)
        if price and price > 0:
            price_factor = max(0.8, min(1.1, 1000 / price))
            score *= price_factor

        return round(score, 4)

    @staticmethod
    def rank_products(
        products: List[Dict[str, Any]],
        query: str = "",
    ) -> List[Dict[str, Any]]:
        """Rank a list of product dicts by composite score."""
        for p in products:
            relevance = 1.0
            if query:
                name = (p.get("name") or "").lower()
                article = (p.get("article") or "").lower()
                q = query.lower()
                if q == article:
                    relevance = 3.0
                elif article.startswith(q):
                    relevance = 2.5
                elif q in name:
                    relevance = 2.0
                elif any(word in name for word in q.split()):
                    relevance = 1.5

            p["_ranking_score"] = RankingEngine.calculate_score(p, relevance)

        products.sort(key=lambda p: p.get("_ranking_score", 0), reverse=True)
        return products

    @staticmethod
    async def get_premium_products(
        category_id: Optional[str] = None,
        limit: int = 10,
        db: AsyncSession = None,
    ) -> List[Dict[str, Any]]:
        """Get premium products for placement."""
        query = select(Product).where(
            Product.is_premium == True,
            Product.is_active == True,
            Product.stock_quantity > 0,
        )
        if category_id:
            query = query.where(Product.category_id == category_id)

        query = query.limit(limit)
        result = await db.execute(query)
        products = result.scalars().all()

        return [
            {
                "id": p.id,
                "article": p.article,
                "name": p.name,
                "price": p.price,
                "is_premium": True,
                "stock_quantity": p.stock_quantity,
                "brand": getattr(p, "brand", None),
            }
            for p in products
        ]


# ── STO Lead-Fee ────────────────────────────────────────────────────

LEAD_FEE_PER_BOOKING = 500  # RUB
LEAD_FEE_PERCENT = 3.0  # % of service price


class LeadFeeEngine:
    """Calculate and track STO lead fees."""

    @staticmethod
    def calculate_lead_fee(service_price: float, booking_type: str = "installation") -> Dict[str, Any]:
        """Calculate lead fee for a service booking."""
        fee_amount = max(
            LEAD_FEE_PER_BOOKING,
            round(service_price * LEAD_FEE_PERCENT / 100, 2),
        )

        return {
            "service_price": service_price,
            "booking_type": booking_type,
            "lead_fee": fee_amount,
            "fee_type": "fixed" if fee_amount == LEAD_FEE_PER_BOOKING else "percentage",
            "currency": "RUB",
        }

    @staticmethod
    async def get_partner_lead_fees(
        partner_id: str,
        period_start: datetime = None,
        period_end: datetime = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """Get lead fee summary for a service partner."""
        from app.models.service import InstallationBooking

        query = select(InstallationBooking).where(
            InstallationBooking.partner_id == partner_id,
        )
        if period_start:
            query = query.where(InstallationBooking.created_at >= period_start)
        if period_end:
            query = query.where(InstallationBooking.created_at <= period_end)

        result = await db.execute(query)
        bookings = result.scalars().all()

        total_fees = 0.0
        total_bookings = len(bookings)
        completed_bookings = 0

        for b in bookings:
            price = b.price or 0
            fee = LeadFeeEngine.calculate_lead_fee(price).get("lead_fee", LEAD_FEE_PER_BOOKING)
            total_fees += fee
            if b.status == "completed":
                completed_bookings += 1

        partner_result = await db.execute(select(ServicePartner).where(ServicePartner.id == partner_id))
        partner = partner_result.scalar_one_or_none()

        return {
            "partner_id": partner_id,
            "partner_name": partner.company_name if partner else "Unknown",
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "total_bookings": total_bookings,
            "completed_bookings": completed_bookings,
            "total_lead_fees": round(total_fees, 2),
            "average_fee_per_booking": round(total_fees / total_bookings, 2) if total_bookings else 0,
        }
