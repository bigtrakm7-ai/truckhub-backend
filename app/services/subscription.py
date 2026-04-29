"""Paid analytics subscription service.

Tiers:
- free: basic metrics only
- basic: + supplier analytics, + export
- pro: + competitor analysis, + API access
- enterprise: + custom reports, + dedicated support
"""

from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from app.core.logging import get_logger

logger = get_logger(__name__)


class SubscriptionTier(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# Feature matrix by tier
FEATURE_MATRIX = {
    "dashboard_basic": [SubscriptionTier.FREE, SubscriptionTier.BASIC, SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE],
    "dashboard_advanced": [SubscriptionTier.BASIC, SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE],
    "export_csv": [SubscriptionTier.BASIC, SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE],
    "export_pdf": [SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE],
    "competitor_analysis": [SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE],
    "api_access": [SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE],
    "custom_reports": [SubscriptionTier.ENTERPRISE],
    "dedicated_support": [SubscriptionTier.ENTERPRISE],
}

# Rate limits by tier (requests per minute)
RATE_LIMITS = {
    SubscriptionTier.FREE: 10,
    SubscriptionTier.BASIC: 60,
    SubscriptionTier.PRO: 300,
    SubscriptionTier.ENTERPRISE: 1000,
}


class SubscriptionService:
    """Manage analytics subscriptions and feature access."""
    
    @staticmethod
    def check_feature_access(tier: SubscriptionTier, feature: str) -> bool:
        """Check if a tier has access to a feature."""
        allowed_tiers = FEATURE_MATRIX.get(feature, [])
        return tier in allowed_tiers
    
    @staticmethod
    def get_rate_limit(tier: SubscriptionTier) -> int:
        """Get API rate limit for tier."""
        return RATE_LIMITS.get(tier, 10)
    
    @staticmethod
    def get_tier_features(tier: SubscriptionTier) -> Dict[str, bool]:
        """Get all features available for a tier."""
        return {
            feature: tier in allowed_tiers
            for feature, allowed_tiers in FEATURE_MATRIX.items()
        }
    
    @staticmethod
    def enforce_analytics_access(
        user_tier: SubscriptionTier,
        requested_feature: str,
    ) -> Dict[str, Any]:
        """Enforce subscription limits on analytics endpoints."""
        has_access = SubscriptionService.check_feature_access(user_tier, requested_feature)
        
        if not has_access:
            allowed_tiers = FEATURE_MATRIX.get(requested_feature, [])
            upgrade_to = allowed_tiers[0] if allowed_tiers else SubscriptionTier.BASIC
            
            return {
                "allowed": False,
                "current_tier": user_tier,
                "required_tier": upgrade_to,
                "message": f"This feature requires {upgrade_to.value} subscription or higher.",
                "upgrade_url": f"/billing/upgrade?to={upgrade_to.value}",
            }
        
        return {
            "allowed": True,
            "tier": user_tier,
            "feature": requested_feature,
        }
    
    @staticmethod
    async def get_subscription_status(user_id: str, db) -> Dict[str, Any]:
        """Get user's current subscription status."""
        # Query subscription from DB (placeholder)
        # In real implementation, query Subscription model
        
        return {
            "user_id": user_id,
            "tier": SubscriptionTier.FREE,  # Default
            "expires_at": None,
            "features": SubscriptionService.get_tier_features(SubscriptionTier.FREE),
            "rate_limit": SubscriptionService.get_rate_limit(SubscriptionTier.FREE),
        }
    
    @staticmethod
    def get_pricing() -> Dict[str, Any]:
        """Get subscription pricing information."""
        return {
            SubscriptionTier.FREE: {
                "price_rub": 0,
                "price_usd": 0,
                "description": "Basic dashboard access",
                "features": ["dashboard_basic"],
            },
            SubscriptionTier.BASIC: {
                "price_rub": 990,
                "price_usd": 12,
                "description": "Advanced analytics + CSV export",
                "features": ["dashboard_basic", "dashboard_advanced", "export_csv"],
            },
            SubscriptionTier.PRO: {
                "price_rub": 2990,
                "price_usd": 35,
                "description": "Competitor analysis + API access",
                "features": [
                    "dashboard_basic", "dashboard_advanced", "export_csv",
                    "export_pdf", "competitor_analysis", "api_access",
                ],
            },
            SubscriptionTier.ENTERPRISE: {
                "price_rub": 9990,
                "price_usd": 120,
                "description": "Custom reports + dedicated support",
                "features": list(FEATURE_MATRIX.keys()),
            },
        }


# Decorator for enforcing subscription
def require_subscription(feature: str):
    """Decorator to enforce subscription tier for a feature."""
    from functools import wraps
    from fastapi import HTTPException, Depends
    from app.api.auth import get_current_active_user
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user = Depends(get_current_active_user), **kwargs):
            # Get user's subscription tier (simplified)
            tier = getattr(current_user, "analytics_tier", SubscriptionTier.FREE)
            
            result = SubscriptionService.enforce_analytics_access(tier, feature)
            
            if not result["allowed"]:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "message": result["message"],
                        "current_tier": result["current_tier"],
                        "required_tier": result["required_tier"],
                        "upgrade_url": result["upgrade_url"],
                    }
                )
            
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator
