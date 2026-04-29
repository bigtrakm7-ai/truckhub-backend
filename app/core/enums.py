from enum import Enum


class UserRole(str, Enum):
    GUEST = "guest"
    BUYER = "buyer"
    SUPPLIER = "supplier"
    SERVICE = "service"
    MANAGER = "manager"
    ADMIN = "admin"


class OrderStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ReturnStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"


class PaymentStatus(str, Enum):
    AWAITING = "awaiting"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
