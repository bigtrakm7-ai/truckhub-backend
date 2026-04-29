# API package
from app.api.auth import router as auth_router
from app.api.products import router as products_router
from app.api.orders import router as orders_router
from app.api.garage import router as garage_router
from app.api.documents import router as documents_router
from app.api.supplier import router as supplier_router
from app.api.catalog import router as catalog_router
from app.api.admin import router as admin_router
from app.api.checkout import router as checkout_router
from app.api.service import router as service_router
from app.api.rma import router as rma_router
from app.api.b2b import router as b2b_router
from app.api.integration import router as integration_router
from app.api.chat import router as chat_router
from app.api.warranty import router as warranty_router
from app.api.reviews import router as reviews_router
from app.api.analytics import router as analytics_router
