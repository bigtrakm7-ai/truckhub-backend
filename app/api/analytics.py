from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, case
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.core.database import get_db
from app.api.auth import require_roles
from app.models.order import Order, OrderItem
from app.models.user import User
from app.models.supplier import Supplier
from app.models.product import Product
from app.models.review import Review
from app.core.enums import UserRole, OrderStatus

router = APIRouter(prefix="/analytics", tags=["Аналитика"])


class DashboardStats(BaseModel):
    total_orders: int
    total_revenue: float
    total_users: int
    total_suppliers: int
    pending_orders: int
    today_orders: int
    today_revenue: float


class OrderStatusStats(BaseModel):
    status: str
    count: int
    revenue: float


class TopProduct(BaseModel):
    product_id: str
    product_name: str
    supplier_name: str
    total_sold: int
    total_revenue: float


class TopSupplier(BaseModel):
    supplier_id: str
    supplier_name: str
    total_orders: int
    total_revenue: float
    average_rating: float


class MonthlyRevenue(BaseModel):
    month: str
    revenue: float
    orders_count: int


class AnalyticsDashboard(BaseModel):
    stats: DashboardStats
    order_status_stats: List[OrderStatusStats]
    top_products: List[TopProduct]
    top_suppliers: List[TopSupplier]
    monthly_revenue: List[MonthlyRevenue]


@router.get("/dashboard", response_model=AnalyticsDashboard)
def get_dashboard_analytics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(UserRole.ADMIN))
):
    # Базовая статистика
    total_orders = db.query(Order).count()
    total_revenue = db.query(func.sum(Order.total_amount)).scalar() or 0
    total_users = db.query(User).filter(User.role == UserRole.BUYER).count()
    total_suppliers = db.query(Supplier).count()
    pending_orders = db.query(Order).filter(Order.status == OrderStatus.PENDING).count()
    
    # Статистика за сегодня
    today = datetime.utcnow().date()
    today_orders_query = db.query(Order).filter(
        func.date(Order.created_at) == today
    )
    today_orders = today_orders_query.count()
    today_revenue = today_orders_query.with_entities(
        func.sum(Order.total_amount)
    ).scalar() or 0
    
    stats = DashboardStats(
        total_orders=total_orders,
        total_revenue=round(total_revenue, 2),
        total_users=total_users,
        total_suppliers=total_suppliers,
        pending_orders=pending_orders,
        today_orders=today_orders,
        today_revenue=round(today_revenue, 2)
    )
    
    # Статистика по статусам заказов
    status_stats = []
    for status in OrderStatus:
        count = db.query(Order).filter(Order.status == status).count()
        revenue = db.query(func.sum(Order.total_amount)).filter(
            Order.status == status
        ).scalar() or 0
        status_stats.append(OrderStatusStats(
            status=status.value,
            count=count,
            revenue=round(revenue, 2)
        ))
    
    # Топ товаров
    top_products_query = db.query(
        OrderItem.product_id,
        func.sum(OrderItem.quantity).label('total_sold'),
        func.sum(OrderItem.total_price).label('total_revenue')
    ).group_by(OrderItem.product_id).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(10).all()
    
    top_products = []
    for item in top_products_query:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        supplier = db.query(Supplier).filter(
            Supplier.id == product.supplier_id
        ).first() if product else None
        
        top_products.append(TopProduct(
            product_id=item.product_id,
            product_name=product.name if product else "Unknown",
            supplier_name=supplier.company_name if supplier else "Unknown",
            total_sold=int(item.total_sold),
            total_revenue=round(float(item.total_revenue), 2)
        ))
    
    # Топ поставщиков
    top_suppliers_query = db.query(
        OrderItem.supplier_id,
        func.count(func.distinct(OrderItem.order_id)).label('total_orders'),
        func.sum(OrderItem.total_price).label('total_revenue')
    ).group_by(OrderItem.supplier_id).order_by(
        func.sum(OrderItem.total_price).desc()
    ).limit(10).all()
    
    top_suppliers = []
    for item in top_suppliers_query:
        supplier = db.query(Supplier).filter(
            Supplier.id == item.supplier_id
        ).first()
        
        # Получаем рейтинг поставщика
        from app.models.review import SupplierRating
        rating = db.query(SupplierRating).filter(
            SupplierRating.supplier_id == item.supplier_id
        ).first()
        
        top_suppliers.append(TopSupplier(
            supplier_id=item.supplier_id,
            supplier_name=supplier.company_name if supplier else "Unknown",
            total_orders=int(item.total_orders),
            total_revenue=round(float(item.total_revenue), 2),
            average_rating=round(rating.average_rating, 2) if rating else 0.0
        ))
    
    # Месячная выручка за последние N дней
    start_date = datetime.utcnow() - timedelta(days=days)
    monthly_data = db.query(
        extract('year', Order.created_at).label('year'),
        extract('month', Order.created_at).label('month'),
        func.sum(Order.total_amount).label('revenue'),
        func.count(Order.id).label('orders_count')
    ).filter(
        Order.created_at >= start_date
    ).group_by(
        extract('year', Order.created_at),
        extract('month', Order.created_at)
    ).order_by(
        extract('year', Order.created_at),
        extract('month', Order.created_at)
    ).all()
    
    monthly_revenue = []
    for item in monthly_data:
        month_name = f"{int(item.year)}-{int(item.month):02d}"
        monthly_revenue.append(MonthlyRevenue(
            month=month_name,
            revenue=round(float(item.revenue), 2),
            orders_count=int(item.orders_count)
        ))
    
    return AnalyticsDashboard(
        stats=stats,
        order_status_stats=status_stats,
        top_products=top_products,
        top_suppliers=top_suppliers,
        monthly_revenue=monthly_revenue
    )


@router.get("/suppliers/{supplier_id}/performance")
def get_supplier_performance(
    supplier_id: str,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(UserRole.ADMIN, UserRole.SUPPLIER))
):
    """Аналитика по конкретному поставщику"""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Заказы поставщика
    orders_count = db.query(OrderItem).filter(
        OrderItem.supplier_id == supplier_id,
        OrderItem.created_at >= start_date
    ).count()
    
    # Выручка
    revenue = db.query(func.sum(OrderItem.total_price)).filter(
        OrderItem.supplier_id == supplier_id,
        OrderItem.created_at >= start_date
    ).scalar() or 0
    
    # Средний чек
    avg_order = db.query(func.avg(OrderItem.total_price)).filter(
        OrderItem.supplier_id == supplier_id,
        OrderItem.created_at >= start_date
    ).scalar() or 0
    
    # Количество уникальных покупателей
    unique_buyers = db.query(func.count(func.distinct(Order.user_id))).join(
        OrderItem, OrderItem.order_id == Order.id
    ).filter(
        OrderItem.supplier_id == supplier_id,
        Order.created_at >= start_date
    ).scalar()
    
    # Отзывы
    reviews_count = db.query(Review).filter(
        Review.supplier_id == supplier_id
    ).count()
    
    avg_rating = db.query(func.avg(Review.rating)).filter(
        Review.supplier_id == supplier_id
    ).scalar() or 0
    
    return {
        "supplier_id": supplier_id,
        "period_days": days,
        "orders_count": orders_count,
        "total_revenue": round(float(revenue), 2),
        "average_order_value": round(float(avg_order), 2),
        "unique_buyers": unique_buyers,
        "reviews_count": reviews_count,
        "average_rating": round(float(avg_rating), 2)
    }


@router.get("/export/orders")
def export_orders_csv(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(UserRole.ADMIN))
):
    """Экспорт заказов в CSV формате"""
    
    query = db.query(Order)
    
    if start_date:
        query = query.filter(Order.created_at >= start_date)
    if end_date:
        query = query.filter(Order.created_at <= end_date)
    
    orders = query.all()
    
    # Формируем CSV
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Заголовки
    writer.writerow([
        "Order ID", "Order Number", "Buyer ID", "Status",
        "Total Amount", "Created At", "Delivery Address"
    ])
    
    # Данные
    for order in orders:
        writer.writerow([
            order.id,
            order.order_number,
            order.user_id,
            order.status.value,
            order.total_amount,
            order.created_at.isoformat(),
            order.delivery_address or ""
        ])
    
    output.seek(0)
    
    from fastapi.responses import StreamingResponse
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders_export.csv"}
    )
