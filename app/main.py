from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, text

from app.api import (
    admin_router,
    analytics_router,
    auth_router,
    b2b_router,
    catalog_router,
    chat_router,
    checkout_router,
    documents_router,
    garage_router,
    integration_router,
    orders_router,
    products_router,
    reviews_router,
    rma_router,
    service_router,
    supplier_router,
    warranty_router,
)
from app.api.support import router as support_router
from app.api.websocket import router as websocket_router
from app.api.metrics import router as metrics_router, PrometheusMiddleware
from app.core.config import settings
from app.core.database import Base, async_session_maker, engine, get_redis, get_elasticsearch, close_db
from app.core.logging import get_logger, setup_logging
from app.core.security_middleware import RateLimitMiddleware, SecurityHeadersMiddleware, AuditLogMiddleware
from app.models.product import Brand, Category, Product, ProductType, StockStatus
from app.models.supplier import Supplier
import app.models

setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)


async def seed_demo_data():
    async with async_session_maker() as session:
        products_count = await session.scalar(select(func.count(Product.id))) or 0
        if products_count > 0:
            return

        supplier = Supplier(
            id=str(uuid4()),
            company_name="TruckHub Demo Supplier",
            inn="7701000000",
            address="Москва",
            warehouse_address="Московская область",
            is_verified=True,
            rating=4.8,
            balance=0.0,
            commission_rate=0.05,
        )

        category = Category(
            id=str(uuid4()),
            name="Двигатель",
            slug="engine",
            description="Детали двигателя для грузовых автомобилей",
        )

        brand = Brand(
            id=str(uuid4()),
            name="Cummins",
            slug="cummins",
            country="USA",
        )

        session.add_all([supplier, category, brand])
        await session.flush()

        demo_products = [
            Product(
                id=str(uuid4()),
                article="250621OEM",
                name="Комплект прокладок двигателя Cummins ISX",
                description="Набор оригинальных прокладок для сервисного ремонта двигателя Cummins ISX.",
                category_id=category.id,
                brand_id=brand.id,
                supplier_id=supplier.id,
                price=12500,
                old_price=13900,
                stock_quantity=14,
                stock_status=StockStatus.IN_STOCK,
                product_type=ProductType.ORIGINAL,
                is_premium=True,
                is_active=True,
                applicability="Cummins ISX, ISX15, тягачи и магистральные грузовики",
            ),
            Product(
                id=str(uuid4()),
                article="P551315",
                name="Фильтр масляный Donaldson P551315",
                description="Фильтр для регулярного технического обслуживания грузового транспорта.",
                category_id=category.id,
                brand_id=brand.id,
                supplier_id=supplier.id,
                price=1700,
                old_price=1950,
                stock_quantity=48,
                stock_status=StockStatus.IN_STOCK,
                product_type=ProductType.ANALOG,
                is_premium=False,
                is_active=True,
                applicability="Cummins, Freightliner, Kenworth, Peterbilt",
            ),
            Product(
                id=str(uuid4()),
                article="FH12-BRK-204",
                name="Колодки тормозные Volvo FH/FM комплект",
                description="Комплект тормозных колодок для коммерческих грузовиков Volvo.",
                category_id=category.id,
                brand_id=brand.id,
                supplier_id=supplier.id,
                price=8900,
                old_price=9400,
                stock_quantity=9,
                stock_status=StockStatus.IN_STOCK,
                product_type=ProductType.ANALOG,
                is_premium=False,
                is_active=True,
                applicability="Volvo FH12, FM12, FMX",
            ),
        ]

        session.add_all(demo_products)
        await session.commit()


async def normalize_legacy_user_roles():
    async with async_session_maker() as session:
        await session.execute(
            text(
                "UPDATE users SET role = lower(role) "
                "WHERE role IN ('GUEST', 'BUYER', 'SUPPLIER', 'SERVICE', 'MANAGER', 'ADMIN')"
            )
        )
        await session.commit()


async def run_legacy_schema_updates():
    async with async_session_maker() as session:
        columns_result = await session.execute(text("PRAGMA table_info(price_uploads)"))
        columns = {row[1] for row in columns_result.fetchall()}
        if "import_kind" not in columns:
            await session.execute(text("ALTER TABLE price_uploads ADD COLUMN import_kind VARCHAR DEFAULT 'products'"))

        order_columns_result = await session.execute(text("PRAGMA table_info(orders)"))
        order_columns = {row[1] for row in order_columns_result.fetchall()}
        if "payment_method" not in order_columns:
            await session.execute(text("ALTER TABLE orders ADD COLUMN payment_method VARCHAR"))
        if "payment_status" not in order_columns:
            await session.execute(text("ALTER TABLE orders ADD COLUMN payment_status VARCHAR DEFAULT 'pending'"))
        if "payment_url" not in order_columns:
            await session.execute(text("ALTER TABLE orders ADD COLUMN payment_url VARCHAR"))
        if "buyer_name" not in order_columns:
            await session.execute(text("ALTER TABLE orders ADD COLUMN buyer_name VARCHAR"))
        if "buyer_phone" not in order_columns:
            await session.execute(text("ALTER TABLE orders ADD COLUMN buyer_phone VARCHAR"))
        if "recipient_name" not in order_columns:
            await session.execute(text("ALTER TABLE orders ADD COLUMN recipient_name VARCHAR"))
        if "recipient_phone" not in order_columns:
            await session.execute(text("ALTER TABLE orders ADD COLUMN recipient_phone VARCHAR"))

        order_item_columns_result = await session.execute(text("PRAGMA table_info(order_items)"))
        order_item_columns = {row[1] for row in order_item_columns_result.fetchall()}
        if "supplier_name" not in order_item_columns:
            await session.execute(text("ALTER TABLE order_items ADD COLUMN supplier_name VARCHAR"))
        if "shipment_status" not in order_item_columns:
            await session.execute(text("ALTER TABLE order_items ADD COLUMN shipment_status VARCHAR DEFAULT 'pending'"))
        if "shipment_tracking_number" not in order_item_columns:
            await session.execute(text("ALTER TABLE order_items ADD COLUMN shipment_tracking_number VARCHAR"))
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await run_legacy_schema_updates()
    await normalize_legacy_user_roles()
    await seed_demo_data()

    await get_redis()
    await get_elasticsearch()

    logger.info("app_startup_complete", extra={"extra": {"env": settings.ENV}})

    yield

    await close_db()
    logger.info("app_shutdown_complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Маркетплейс запчастей для грузового транспорта",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENV == "dev" else [
        "https://truckhub-frontend-rfj0vzqox-bigtrakm7-6887s-projects.vercel.app",
        "https://truckhub-frontend-phi.vercel.app",
        "https://truckhub.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuditLogMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
app.add_middleware(PrometheusMiddleware)

app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(products_router, prefix=settings.API_PREFIX)
app.include_router(orders_router, prefix=settings.API_PREFIX)
app.include_router(garage_router, prefix=settings.API_PREFIX)
app.include_router(documents_router, prefix=settings.API_PREFIX)
app.include_router(supplier_router, prefix=settings.API_PREFIX)
app.include_router(catalog_router, prefix=settings.API_PREFIX)
app.include_router(admin_router, prefix=settings.API_PREFIX)
app.include_router(checkout_router, prefix=settings.API_PREFIX)
app.include_router(service_router, prefix=settings.API_PREFIX)
app.include_router(rma_router, prefix=settings.API_PREFIX)
app.include_router(b2b_router, prefix=settings.API_PREFIX)
app.include_router(integration_router, prefix=settings.API_PREFIX)
app.include_router(chat_router, prefix=settings.API_PREFIX)
app.include_router(warranty_router, prefix=settings.API_PREFIX)
app.include_router(support_router, prefix=settings.API_PREFIX)
app.include_router(websocket_router, prefix=settings.API_PREFIX)
app.include_router(metrics_router, prefix="")
app.include_router(reviews_router, prefix=settings.API_PREFIX)
app.include_router(analytics_router, prefix=settings.API_PREFIX)


@app.get("/health")
async def health_check():
    from app.services.integration_service import integration_service
    redis_client = await get_redis()
    es_client = await get_elasticsearch()

    return {
        "status": "healthy",
        "env": settings.ENV,
        "version": settings.VERSION,
        "database": "connected",
        "redis": "connected" if redis_client else "unavailable",
        "elasticsearch": "connected" if es_client else "unavailable",
        "providers": integration_service.providers_health(),
    }


@app.get("/")
async def root():
    return {"message": "TruckHub API"}