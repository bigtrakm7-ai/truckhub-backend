from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CreditApplicationCreate(BaseModel):
    amount: float
    term_months: int
    purpose: str
    inn: str


class CreditApplicationResponse(BaseModel):
    id: str
    user_id: str
    amount: float
    term_months: int
    purpose: str
    status: str
    approved_amount: Optional[float] = None
    interest_rate: Optional[float] = None
    monthly_payment: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentDeferralRequest(BaseModel):
    order_id: str
    defer_days: int
    reason: str


class PaymentDeferralResponse(BaseModel):
    id: str
    user_id: str
    order_id: str
    defer_days: int
    status: str
    approved_until: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class QuoteRequestItem(BaseModel):
    product_id: str
    quantity: int
    target_price: Optional[float] = None


class QuoteRequestCreate(BaseModel):
    title: str
    comment: Optional[str] = None
    need_by_date: Optional[datetime] = None
    items: List[QuoteRequestItem]


class QuoteRequestResponse(BaseModel):
    id: str
    user_id: str
    title: str
    comment: Optional[str] = None
    status: str
    need_by_date: Optional[datetime] = None
    items: List[QuoteRequestItem]
    total_items: int
    created_at: datetime

    class Config:
        from_attributes = True


class PromocodeCreate(BaseModel):
    code: str
    discount_type: str
    discount_value: float
    min_order_amount: Optional[float] = None
    max_uses: Optional[int] = None
    valid_from: datetime
    valid_to: datetime


class PromocodeResponse(BaseModel):
    id: str
    code: str
    discount_type: str
    discount_value: float
    min_order_amount: Optional[float] = None
    max_uses: Optional[int] = None
    uses_count: int
    is_active: bool
    valid_from: datetime
    valid_to: datetime

    class Config:
        from_attributes = True


class ReferralProgramResponse(BaseModel):
    referral_code: str
    referral_link: str
    referrals_count: int
    earned_amount: float
    pending_amount: float
