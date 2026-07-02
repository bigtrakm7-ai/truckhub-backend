from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import uuid

from app.core.database import get_db
from app.api.auth import get_current_user, require_roles
from app.models.review import Review, SupplierRating
from app.models.order import Order, OrderItem
from app.models.supplier import Supplier
from app.models.user import User
from app.core.enums import UserRole
from app.core.messages import Msg

router = APIRouter(prefix="/reviews", tags=["Отзывы"])


class ReviewCreate(BaseModel):
    order_id: str
    shipment_id: Optional[str] = None
    supplier_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class ReviewResponse(BaseModel):
    id: str
    order_id: str
    shipment_id: Optional[str]
    buyer_id: str
    supplier_id: str
    rating: int
    comment: Optional[str]
    is_approved: bool
    is_visible: bool
    admin_reply: Optional[str]
    admin_reply_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ReviewWithBuyer(ReviewResponse):
    buyer_name: Optional[str]
    buyer_company: Optional[str]


class SupplierRatingResponse(BaseModel):
    supplier_id: str
    supplier_name: str
    total_reviews: int
    average_rating: float
    rating_5_count: int
    rating_4_count: int
    rating_3_count: int
    rating_2_count: int
    rating_1_count: int


@router.post("/", response_model=ReviewResponse)
def create_review(
    data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Проверяем что заказ существует и принадлежит buyer
    order = db.query(Order).filter(
        Order.id == data.order_id,
        Order.user_id == current_user.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail=Msg.ORDER_NOT_FOUND)
    
    # Проверяем что заказ завершен
    if order.status.value not in ["delivered", "completed"]:
        raise HTTPException(status_code=400, detail="Отзыв можно оставить только после доставки")
    
    # Проверяем что отзыв еще не оставлен
    existing = db.query(Review).filter(
        Review.order_id == data.order_id,
        Review.buyer_id == current_user.id,
        Review.supplier_id == data.supplier_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Отзыв уже оставлен")
    
    review = Review(
        id=str(uuid.uuid4()),
        order_id=data.order_id,
        shipment_id=data.shipment_id,
        buyer_id=current_user.id,
        supplier_id=data.supplier_id,
        rating=data.rating,
        comment=data.comment
    )
    
    db.add(review)
    db.commit()
    db.refresh(review)
    
    # Обновляем рейтинг поставщика
    update_supplier_rating(data.supplier_id, db)
    
    return review


@router.get("/supplier/{supplier_id}", response_model=List[ReviewWithBuyer])
def get_supplier_reviews(
    supplier_id: str,
    approved_only: bool = Query(True),
    db: Session = Depends(get_db)
):
    query = db.query(Review).filter(
        Review.supplier_id == supplier_id,
        Review.is_visible == True
    )
    
    if approved_only:
        query = query.filter(Review.is_approved == True)
    
    reviews = query.order_by(Review.created_at.desc()).all()
    
    result = []
    for review in reviews:
        buyer = db.query(User).filter(User.id == review.buyer_id).first()
        review_data = ReviewWithBuyer(
            **review.__dict__,
            buyer_name=buyer.company_name if buyer else None,
            buyer_company=buyer.company_name if buyer else None
        )
        result.append(review_data)
    
    return result


@router.get("/supplier/{supplier_id}/rating", response_model=SupplierRatingResponse)
def get_supplier_rating(supplier_id: str, db: Session = Depends(get_db)):
    rating = db.query(SupplierRating).filter(
        SupplierRating.supplier_id == supplier_id
    ).first()
    
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    
    if not rating:
        return SupplierRatingResponse(
            supplier_id=supplier_id,
            supplier_name=supplier.company_name if supplier else "Unknown",
            total_reviews=0,
            average_rating=0.0,
            rating_5_count=0,
            rating_4_count=0,
            rating_3_count=0,
            rating_2_count=0,
            rating_1_count=0
        )
    
    return SupplierRatingResponse(
        supplier_id=supplier_id,
        supplier_name=supplier.company_name if supplier else "Unknown",
        total_reviews=rating.total_reviews,
        average_rating=round(rating.average_rating, 2),
        rating_5_count=rating.rating_5_count,
        rating_4_count=rating.rating_4_count,
        rating_3_count=rating.rating_3_count,
        rating_2_count=rating.rating_2_count,
        rating_1_count=rating.rating_1_count
    )


@router.put("/{review_id}/approve", response_model=ReviewResponse)
def approve_review(
    review_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN))
):
    review = db.query(Review).filter(Review.id == review_id).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")
    
    review.is_approved = True
    db.commit()
    db.refresh(review)
    
    return review


@router.post("/{review_id}/reply", response_model=ReviewResponse)
def admin_reply(
    review_id: str,
    reply: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN))
):
    review = db.query(Review).filter(Review.id == review_id).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")
    
    review.admin_reply = reply
    review.admin_reply_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    
    return review


@router.delete("/{review_id}")
def delete_review(
    review_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    review = db.query(Review).filter(Review.id == review_id).first()
    
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")
    
    # Только автор или админ может удалить
    if review.buyer_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail=Msg.ACCESS_DENIED)
    
    supplier_id = review.supplier_id
    
    db.delete(review)
    db.commit()
    
    # Обновляем рейтинг поставщика
    update_supplier_rating(supplier_id, db)
    
    return {"status": "deleted"}


def update_supplier_rating(supplier_id: str, db: Session):
    """Обновляет агрегированный рейтинг поставщика"""
    
    reviews = db.query(Review).filter(
        Review.supplier_id == supplier_id,
        Review.is_approved == True
    ).all()
    
    rating = db.query(SupplierRating).filter(
        SupplierRating.supplier_id == supplier_id
    ).first()
    
    if not rating:
        rating = SupplierRating(
            id=str(uuid.uuid4()),
            supplier_id=supplier_id
        )
        db.add(rating)
    
    if not reviews:
        rating.total_reviews = 0
        rating.average_rating = 0.0
        rating.rating_5_count = 0
        rating.rating_4_count = 0
        rating.rating_3_count = 0
        rating.rating_2_count = 0
        rating.rating_1_count = 0
    else:
        total = len(reviews)
        avg = sum(r.rating for r in reviews) / total
        
        rating.total_reviews = total
        rating.average_rating = avg
        rating.rating_5_count = sum(1 for r in reviews if r.rating == 5)
        rating.rating_4_count = sum(1 for r in reviews if r.rating == 4)
        rating.rating_3_count = sum(1 for r in reviews if r.rating == 3)
        rating.rating_2_count = sum(1 for r in reviews if r.rating == 2)
        rating.rating_1_count = sum(1 for r in reviews if r.rating == 1)
    
    db.commit()
