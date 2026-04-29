import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.auth import get_current_active_user
from app.api.b2b import quote_requests_storage
from app.core.database import get_db
from app.core.enums import UserRole
from app.core.rbac import require_roles
from app.main import app
from app.services.delivery_schema import validate_delivery_payload
from app.api.catalog import _fuzzy_match_score
from app.api.catalog import _compatibility_score
from app.api.catalog import _bundle_recommendation_score
from app.api.service import _normalize_booking_status, _can_transition_booking_status
from app.services.notification_schema import validate_notification_payload
from app.services.integration_service import integration_service


class TestRBAC(unittest.TestCase):
    def test_require_roles_allows_admin(self):
        guard = require_roles(UserRole.ADMIN)
        user = SimpleNamespace(role=UserRole.ADMIN)
        result = asyncio.run(guard(current_user=user))
        self.assertEqual(result, user)

    def test_require_roles_denies_buyer(self):
        guard = require_roles(UserRole.ADMIN)
        user = SimpleNamespace(role=UserRole.BUYER)
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(guard(current_user=user))
        self.assertEqual(ctx.exception.status_code, 403)


class TestIntegrationSchemas(unittest.TestCase):
    def test_validate_delivery_payload_ok(self):
        req = validate_delivery_payload(
            {
                "provider": "cdek",
                "from_city": "Moscow",
                "to_city": "Kazan",
                "weight_kg": 10,
                "volume_m3": 0.15,
                "delivery_type": "courier",
            }
        )
        self.assertEqual(req.provider, "cdek")
        self.assertEqual(req.to_city, "Kazan")

    def test_validate_delivery_payload_bad_provider(self):
        with self.assertRaises(ValueError):
            validate_delivery_payload(
                {
                    "provider": "unknown",
                    "from_city": "Moscow",
                    "to_city": "Kazan",
                    "weight_kg": 10,
                    "volume_m3": 0.15,
                }
            )

    def test_validate_notification_payload_ok(self):
        p = validate_notification_payload(
            {"channel": "email", "to": "x@example.com", "message": "hello"}
        )
        self.assertEqual(p.channel, "email")

    def test_validate_notification_payload_invalid(self):
        with self.assertRaises(ValueError):
            validate_notification_payload(
                {"channel": "fax", "to": "x@example.com", "message": "hello"}
            )


class TestIntegrationService(unittest.TestCase):
    def test_notification_router_fallback_invalid_channel(self):
        res = integration_service.send_notification(
            channel="invalid", to="x@example.com", message="hello"
        )
        self.assertEqual(res.get("status"), "failed")

    def test_notification_router_success_email(self):
        res = integration_service.send_notification(
            channel="email", to="x@example.com", message="hello"
        )
        self.assertIn(res.get("status"), ("queued", "accepted"))
        self.assertEqual(res.get("channel"), "email")

    def test_delivery_estimate_cdek(self):
        res = integration_service.estimate_delivery(
            {
                "provider": "cdek",
                "from_city": "Moscow",
                "to_city": "Kazan",
                "weight_kg": 12.5,
                "volume_m3": 0.2,
                "delivery_type": "courier",
            }
        )
        self.assertEqual(res["provider"], "cdek")
        self.assertEqual(res["currency"], "RUB")
        self.assertGreater(res["price"], 0)

    def test_delivery_estimate_pec(self):
        res = integration_service.estimate_delivery(
            {
                "provider": "pec",
                "from_city": "Moscow",
                "to_city": "Kazan",
                "weight_kg": 8,
                "volume_m3": 0.12,
            }
        )
        self.assertEqual(res["provider"], "pec")
        self.assertEqual(res["currency"], "RUB")
        self.assertGreaterEqual(res["days"], 1)

    def test_delivery_estimate_delovye_linii(self):
        res = integration_service.estimate_delivery(
            {
                "provider": "delovye_linii",
                "from_city": "Moscow",
                "to_city": "Kazan",
                "weight_kg": 8,
                "volume_m3": 0.12,
            }
        )
        self.assertEqual(res["provider"], "delovye_linii")
        self.assertEqual(res["currency"], "RUB")
        self.assertGreaterEqual(res["days"], 1)

    def test_delivery_estimate_invalid_provider_raises(self):
        with self.assertRaises(ValueError):
            integration_service.estimate_delivery(
                {
                    "provider": "bad",
                    "from_city": "Moscow",
                    "to_city": "Kazan",
                    "weight_kg": 8,
                    "volume_m3": 0.12,
                }
            )


class TestIntegrationApiHttpMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
            id="test-user", is_active=True, role=UserRole.ADMIN
        )
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def test_delivery_estimate_invalid_provider_422(self):
        response = self.client.post(
            "/api/v1/integration/delivery/estimate",
            json={
                "provider": "invalid_provider",
                "from_city": "Moscow",
                "to_city": "Kazan",
                "weight_kg": 10,
                "volume_m3": 0.15,
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_delivery_estimate_runtime_error_502(self):
        with patch(
            "app.api.integration.integration_service.estimate_delivery",
            side_effect=RuntimeError("provider down"),
        ):
            response = self.client.post(
                "/api/v1/integration/delivery/estimate",
                json={
                    "provider": "cdek",
                    "from_city": "Moscow",
                    "to_city": "Kazan",
                    "weight_kg": 10,
                    "volume_m3": 0.15,
                    "delivery_type": "courier",
                },
            )
        self.assertEqual(response.status_code, 502)

    def test_delivery_estimate_success_200(self):
        response = self.client.post(
            "/api/v1/integration/delivery/estimate",
            json={
                "provider": "cdek",
                "from_city": "Moscow",
                "to_city": "Kazan",
                "weight_kg": 10,
                "volume_m3": 0.15,
                "delivery_type": "courier",
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_notifications_invalid_channel_422(self):
        response = self.client.post(
            "/api/v1/integration/notifications/send",
            json={
                "channel": "fax",
                "to": "x@example.com",
                "message": "hello",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_notifications_provider_failed_502(self):
        with patch(
            "app.api.integration.integration_service.send_notification",
            return_value={"status": "failed", "error": "provider down"},
        ):
            response = self.client.post(
                "/api/v1/integration/notifications/send",
                json={
                    "channel": "email",
                    "to": "x@example.com",
                    "message": "hello",
                },
            )
        self.assertEqual(response.status_code, 502)

    def test_notifications_email_success_200(self):
        response = self.client.post(
            "/api/v1/integration/notifications/send",
            json={
                "channel": "email",
                "to": "x@example.com",
                "message": "hello",
            },
        )
        self.assertEqual(response.status_code, 200)


class TestCatalogFuzzySearch(unittest.TestCase):
    def test_fuzzy_score_exact_article_contains(self):
        score = _fuzzy_match_score("A123", "xx-A123-zz", "Oil Filter")
        self.assertGreaterEqual(score, 0.99)

    def test_fuzzy_score_typo_in_name(self):
        score = _fuzzy_match_score("filtre", "B-777", "Oil Filter Premium")
        self.assertGreaterEqual(score, 0.55)

    def test_fuzzy_score_empty_query(self):
        score = _fuzzy_match_score("", "B-777", "Oil Filter Premium")
        self.assertEqual(score, 0.0)


class TestCatalogCrossReferences(unittest.TestCase):
    def test_compatibility_score_higher_for_same_article(self):
        base = SimpleNamespace(article="A-123", name="Oil Filter", brand_id="b1", category_id="c1", product_type="original")
        same = SimpleNamespace(article="A123", name="Oil Filter Premium", brand_id="b1", category_id="c1", product_type="analog")
        diff = SimpleNamespace(article="ZX9", name="Brake Pad", brand_id="b2", category_id="c2", product_type="analog")

        score_same = _compatibility_score(base, same)
        score_diff = _compatibility_score(base, diff)

        self.assertGreater(score_same, score_diff)
        self.assertGreaterEqual(score_same, 0.7)

    def test_compatibility_score_is_capped(self):
        base = SimpleNamespace(article="AAA111", name="Engine Oil Filter", brand_id="b1", category_id="c1", product_type="original")
        candidate = SimpleNamespace(article="AAA111", name="Engine Oil Filter", brand_id="b1", category_id="c1", product_type="analog")

        score = _compatibility_score(base, candidate)
        self.assertLessEqual(score, 0.99)
        self.assertGreaterEqual(score, 0.9)


class TestCatalogBundleRecommendations(unittest.TestCase):
    def test_bundle_score_prefers_same_brand_and_supplier(self):
        base = SimpleNamespace(
            article="A100",
            name="Oil Filter Heavy Duty",
            brand_id="b1",
            supplier_id="s1",
            category_id="c1",
            price=1000,
            stock_quantity=5,
            is_premium=False,
            applicability="actros volvo",
        )
        candidate_good = SimpleNamespace(
            article="M200",
            name="Oil Additive Filter Care",
            brand_id="b1",
            supplier_id="s1",
            category_id="c1",
            price=450,
            stock_quantity=8,
            is_premium=True,
            applicability="actros",
        )
        candidate_weak = SimpleNamespace(
            article="X999",
            name="Brake Disk",
            brand_id="b9",
            supplier_id="s9",
            category_id="c9",
            price=1800,
            stock_quantity=0,
            is_premium=False,
            applicability="",
        )

        score_good, _ = _bundle_recommendation_score(base, candidate_good)
        score_weak, _ = _bundle_recommendation_score(base, candidate_weak)

        self.assertGreater(score_good, score_weak)
        self.assertGreaterEqual(score_good, 0.35)

    def test_bundle_score_is_capped(self):
        base = SimpleNamespace(
            article="A100",
            name="Engine Oil Filter",
            brand_id="b1",
            supplier_id="s1",
            category_id="c1",
            price=1000,
            stock_quantity=5,
            is_premium=False,
            applicability="actros volvo",
        )
        candidate = SimpleNamespace(
            article="A101",
            name="Engine Oil Filter Additive",
            brand_id="b1",
            supplier_id="s1",
            category_id="c1",
            price=300,
            stock_quantity=10,
            is_premium=True,
            applicability="actros volvo",
        )

        score, reason = _bundle_recommendation_score(base, candidate)
        self.assertLessEqual(score, 0.99)
        self.assertGreaterEqual(score, 0.5)
        self.assertIsInstance(reason, str)
        self.assertTrue(len(reason) > 0)


class TestServiceBookingWorkflow(unittest.TestCase):
    def test_normalize_booking_status_ok(self):
        self.assertEqual(_normalize_booking_status(" CONFIRMED "), "confirmed")

    def test_normalize_booking_status_invalid(self):
        with self.assertRaises(HTTPException) as ctx:
            _normalize_booking_status("bad_status")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_booking_status_transition_rules(self):
        self.assertTrue(_can_transition_booking_status("pending", "confirmed"))
        self.assertFalse(_can_transition_booking_status("completed", "pending"))
        self.assertTrue(_can_transition_booking_status("in_progress", "completed"))


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeB2BDB:
    async def execute(self, query):
        return _FakeScalarResult(SimpleNamespace(id="prod-1"))


class TestB2BQuoteWorkflowApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        async def _override_get_db():
            yield _FakeB2BDB()

        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
            id="b2b-user", is_active=True, role=UserRole.BUYER, inn="7701234567"
        )
        app.dependency_overrides[get_db] = _override_get_db
        quote_requests_storage.clear()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        quote_requests_storage.clear()

    def test_create_quote_422_when_items_empty(self):
        response = self.client.post(
            "/api/v1/b2b/quotes",
            json={"title": "Запрос КП", "items": []},
        )
        self.assertEqual(response.status_code, 422)

    def test_create_list_get_quote_success(self):
        create_response = self.client.post(
            "/api/v1/b2b/quotes",
            json={
                "title": "КП на расходники",
                "comment": "Нужно лучшее предложение",
                "items": [
                    {"product_id": "prod-1", "quantity": 2, "target_price": 900.0}
                ],
            },
        )
        self.assertEqual(create_response.status_code, 200)
        quote_id = create_response.json()["id"]

        list_response = self.client.get("/api/v1/b2b/quotes")
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(any(q["id"] == quote_id for q in list_response.json()))

        get_response = self.client.get(f"/api/v1/b2b/quotes/{quote_id}")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["total_items"], 1)


class _FakeDocScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


class _FakeDocumentsDB:
    def __init__(self):
        self.calls = 0

    async def execute(self, query):
        self.calls += 1
        if self.calls == 1:
            order = SimpleNamespace(
                id="ord-doc-1",
                order_number="ORD-1001",
                status="delivered",
                total_amount=12000.0,
            )
            return _FakeDocScalarResult(order)

        items = [
            SimpleNamespace(product_id="prod-a", quantity=1, unit_price=5000.0, total_price=5000.0, is_installation=False),
            SimpleNamespace(product_id="prod-b", quantity=1, unit_price=7000.0, total_price=7000.0, is_installation=True),
        ]
        return _FakeDocScalarResult(items)


class TestDocumentsLifecycleApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        async def _override_get_db():
            yield _FakeDocumentsDB()

        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
            id="doc-user", email="doc@example.com", is_active=True, role=UserRole.BUYER, company_name="OOO Test", inn="7701234567", address="Moscow"
        )
        app.dependency_overrides[get_db] = _override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def test_documents_lifecycle_endpoint_returns_ready_statuses(self):
        response = self.client.get("/api/v1/documents/lifecycle/ord-doc-1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["lifecycle"]["invoice"]["status"], "ready")
        self.assertEqual(payload["lifecycle"]["upd"]["status"], "ready")
        self.assertEqual(payload["lifecycle"]["act"]["status"], "ready")

    def test_invoice_contains_lifecycle(self):
        response = self.client.get("/api/v1/documents/invoice/ord-doc-1")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("lifecycle", payload)
        self.assertEqual(payload["lifecycle"]["invoice"]["available"], True)


if __name__ == "__main__":
    unittest.main()
