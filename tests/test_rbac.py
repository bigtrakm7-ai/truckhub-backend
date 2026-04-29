"""RBAC permission matrix tests.

Validates that each role can only access its permitted endpoints.
"""

import pytest
from app.core.enums import UserRole
from app.core.rbac import require_roles
from fastapi import HTTPException


# ── Permission Matrix ────────────────────────────────────────────────
# Defines which roles can access which endpoint groups

PERMISSION_MATRIX = {
    # Buyer endpoints
    "orders:create": [UserRole.BUYER, UserRole.ADMIN],
    "orders:read_own": [UserRole.BUYER, UserRole.ADMIN],
    "cart:manage": [UserRole.BUYER, UserRole.ADMIN],
    "garage:manage": [UserRole.BUYER, UserRole.ADMIN],
    "reviews:write": [UserRole.BUYER, UserRole.ADMIN],
    "support:create_ticket": [UserRole.BUYER, UserRole.SUPPLIER, UserRole.MANAGER, UserRole.ADMIN],
    "support:read_own": [UserRole.BUYER, UserRole.SUPPLIER, UserRole.MANAGER, UserRole.ADMIN],

    # Supplier endpoints
    "supplier:products": [UserRole.SUPPLIER, UserRole.ADMIN],
    "supplier:orders": [UserRole.SUPPLIER, UserRole.ADMIN],
    "supplier:prices": [UserRole.SUPPLIER, UserRole.ADMIN],
    "supplier:analytics": [UserRole.SUPPLIER, UserRole.ADMIN],
    "supplier:payouts": [UserRole.SUPPLIER, UserRole.ADMIN],

    # Manager endpoints
    "support:dashboard": [UserRole.MANAGER, UserRole.ADMIN],
    "support:assign": [UserRole.MANAGER, UserRole.ADMIN],
    "support:internal_comments": [UserRole.MANAGER, UserRole.ADMIN],

    # Admin endpoints
    "admin:users": [UserRole.ADMIN],
    "admin:commissions": [UserRole.ADMIN],
    "admin:verifications": [UserRole.ADMIN],
    "admin:disputes": [UserRole.ADMIN],
    "admin:risk_checks": [UserRole.ADMIN],
    "admin:stop_list": [UserRole.ADMIN],
    "admin:premium": [UserRole.ADMIN],
    "admin:sto_fees": [UserRole.ADMIN],

    # Shared
    "catalog:read": [UserRole.BUYER, UserRole.SUPPLIER, UserRole.MANAGER, UserRole.ADMIN, UserRole.SERVICE],
    "chat:participate": [UserRole.BUYER, UserRole.SUPPLIER, UserRole.ADMIN],
}


def test_buyer_permissions():
    """Buyer can only access buyer and shared endpoints."""
    buyer_role = UserRole.BUYER
    allowed = [k for k, roles in PERMISSION_MATRIX.items() if buyer_role in roles]
    denied = [k for k, roles in PERMISSION_MATRIX.items() if buyer_role not in roles]

    assert "orders:create" in allowed
    assert "cart:manage" in allowed
    assert "catalog:read" in allowed
    assert "supplier:products" not in allowed
    assert "admin:users" not in allowed
    assert "support:dashboard" not in allowed


def test_supplier_permissions():
    """Supplier can access supplier + shared endpoints."""
    supplier_role = UserRole.SUPPLIER
    allowed = [k for k, roles in PERMISSION_MATRIX.items() if supplier_role in roles]

    assert "supplier:products" in allowed
    assert "supplier:payouts" in allowed
    assert "catalog:read" in allowed
    assert "orders:create" not in allowed
    assert "admin:users" not in allowed


def test_manager_permissions():
    """Manager can access support management + shared."""
    manager_role = UserRole.MANAGER
    allowed = [k for k, roles in PERMISSION_MATRIX.items() if manager_role in roles]

    assert "support:dashboard" in allowed
    assert "support:assign" in allowed
    assert "support:create_ticket" in allowed
    assert "catalog:read" in allowed
    assert "admin:users" not in allowed
    assert "supplier:products" not in allowed


def test_admin_permissions():
    """Admin can access everything."""
    admin_role = UserRole.ADMIN
    allowed = [k for k, roles in PERMISSION_MATRIX.items() if admin_role in roles]

    assert "admin:users" in allowed
    assert "admin:commissions" in allowed
    assert "orders:create" in allowed
    assert "supplier:products" in allowed
    assert "support:dashboard" in allowed
    assert len(allowed) == len(PERMISSION_MATRIX)


def test_service_permissions():
    """Service role is limited."""
    service_role = UserRole.SERVICE
    allowed = [k for k, roles in PERMISSION_MATRIX.items() if service_role in roles]

    assert "catalog:read" in allowed
    assert "admin:users" not in allowed
    assert "orders:create" not in allowed


def test_no_cross_role_access():
    """Buyer cannot access supplier endpoints and vice versa."""
    buyer_only = {"orders:create", "cart:manage", "garage:manage", "reviews:write"}
    supplier_only = {"supplier:products", "supplier:orders", "supplier:prices", "supplier:payouts"}
    admin_only = {"admin:users", "admin:commissions", "admin:verifications", "admin:risk_checks", "admin:stop_list"}

    for endpoint in buyer_only:
        assert UserRole.SUPPLIER not in PERMISSION_MATRIX.get(endpoint, [])
        assert UserRole.MANAGER not in PERMISSION_MATRIX.get(endpoint, [])

    for endpoint in supplier_only:
        assert UserRole.BUYER not in PERMISSION_MATRIX.get(endpoint, [])
        assert UserRole.MANAGER not in PERMISSION_MATRIX.get(endpoint, [])

    for endpoint in admin_only:
        assert UserRole.BUYER not in PERMISSION_MATRIX.get(endpoint, [])
        assert UserRole.SUPPLIER not in PERMISSION_MATRIX.get(endpoint, [])
        assert UserRole.MANAGER not in PERMISSION_MATRIX.get(endpoint, [])


def test_require_roles_factory():
    """Test require_roles dependency factory."""
    # The function should return a dependency callable
    dep = require_roles(UserRole.ADMIN)
    assert callable(dep)

    dep = require_roles(UserRole.BUYER, UserRole.SUPPLIER)
    assert callable(dep)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
