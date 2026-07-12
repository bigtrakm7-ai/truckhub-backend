from typing import Dict, Any, List, Optional

from app.services.vin_provider import MockLaximoProvider, HttpLaximoProvider


class MockPaymentProvider:
    name = "mock_payment"

    def health(self) -> Dict[str, Any]:
        return {"status": "ok", "provider": self.name}


class MockCdekProvider:
    name = "mock_cdek"

    def health(self) -> Dict[str, Any]:
        return {"status": "ok", "provider": self.name}

    def estimate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"provider": "cdek", "price": 620, "days": 2, "currency": "RUB", "delivery_type": payload.get("delivery_type", "courier")}


class MockPecProvider:
    name = "mock_pec"

    def health(self) -> Dict[str, Any]:
        return {"status": "ok", "provider": self.name}

    def estimate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"provider": "pec", "price": 710, "days": 3, "currency": "RUB", "delivery_type": payload.get("delivery_type", "courier")}


class MockDelovyeLiniiProvider:
    name = "mock_delovye_linii"

    def health(self) -> Dict[str, Any]:
        return {"status": "ok", "provider": self.name}

    def estimate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"provider": "delovye_linii", "price": 690, "days": 3, "currency": "RUB", "delivery_type": payload.get("delivery_type", "courier")}


class HttpCdekProvider:
    """Real CDEK API integration.

    Requires env vars: CDEK_ACCOUNT, CDEK_SECURE_PASSWORD (or CDEK_TOKEN for v2).
    Uses CDEK API v2 (https://api.cdek.ru/v2/).
    """
    name = "http_cdek"

    def __init__(self) -> None:
        from app.core.config import settings
        self.account = getattr(settings, "CDEK_ACCOUNT", "")
        self.password = getattr(settings, "CDEK_SECURE_PASSWORD", "")
        self.token = getattr(settings, "CDEK_TOKEN", "")
        self.base_url = getattr(settings, "CDEK_API_URL", "") or "https://api.cdek.ru/v2"

    def health(self) -> Dict[str, Any]:
        configured = bool(self.account and self.password) or bool(self.token)
        return {"status": "ok" if configured else "degraded", "provider": self.name, "configured": configured}

    def _get_token(self) -> str:
        import httpx
        if self.token:
            return self.token
        resp = httpx.post(
            f"{self.base_url}/oauth/token",
            data={"grant_type": "client_credentials"},
            auth=(self.account, self.password),
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def estimate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from app.core.logging import get_logger
        logger = get_logger(__name__)

        try:
            token = self._get_token()
            import httpx

            from_location = payload.get("from_location") or {"code": 44}
            to_location = payload.get("to_location") or {"code": 137}
            packages = payload.get("packages") or [{"weight": payload.get("weight", 1000), "length": 30, "width": 20, "height": 15}]

            calc_body = {
                "type": payload.get("delivery_type", 1),
                "date": payload.get("date"),
                "from_location": from_location,
                "to_location": to_location,
                "packages": packages,
            }

            resp = httpx.post(
                f"{self.base_url}/calculator/tarifflist",
                json=calc_body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()

            tariffs = data.get("tariff_codes") or []
            if tariffs:
                best = tariffs[0]
                return {
                    "provider": "cdek",
                    "tariff_code": best.get("tariff_code"),
                    "price": best.get("delivery_sum", 0),
                    "days_min": best.get("period_min"),
                    "days_max": best.get("period_max"),
                    "currency": "RUB",
                    "delivery_type": payload.get("delivery_type", "courier"),
                }

            return {"provider": "cdek", "price": 0, "days": None, "currency": "RUB", "error": "no tariffs found"}
        except Exception as exc:
            logger.warning("cdek_estimate_failed", extra={"extra": {"error": str(exc)}})
            return MockCdekProvider().estimate(payload)


class HttpPecProvider:
    """Real ПЭК API integration.

    Requires env vars: PEC_API_KEY.
    Uses ПЭК API (https://pecom.ru/api/).
    """
    name = "http_pec"

    def __init__(self) -> None:
        from app.core.config import settings
        self.api_key = getattr(settings, "PEC_API_KEY", "")
        self.base_url = getattr(settings, "PEC_API_URL", "") or "https://pecom.ru/api"

    def health(self) -> Dict[str, Any]:
        configured = bool(self.api_key)
        return {"status": "ok" if configured else "degraded", "provider": self.name, "configured": configured}

    def estimate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from app.core.logging import get_logger
        logger = get_logger(__name__)

        if not self.api_key:
            return MockPecProvider().estimate(payload)

        try:
            import httpx

            calc_body = {
                "cargo": {
                    "weight": payload.get("weight", 1000) / 1000,
                    "volume": payload.get("volume", 0.1),
                    "positions": payload.get("positions", [{"weight": payload.get("weight", 1000) / 1000, "volume": 0.1}]),
                },
                "departure": {"cityId": payload.get("from_city_id", 1)},
                "destination": {"cityId": payload.get("to_city_id", 2)},
                "isInsurance": payload.get("is_insurance", False),
                "isPickUp": payload.get("is_pickup", False),
                "isDelivery": payload.get("is_delivery", True),
            }

            resp = httpx.post(
                f"{self.base_url}/v1/calculation",
                json=calc_body,
                headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"},
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()

            return {
                "provider": "pec",
                "price": data.get("total", data.get("price", 710)),
                "days": data.get("days", data.get("transitDays", 3)),
                "currency": "RUB",
                "delivery_type": payload.get("delivery_type", "terminal"),
            }
        except Exception as exc:
            logger.warning("pec_estimate_failed", extra={"extra": {"error": str(exc)}})
            return MockPecProvider().estimate(payload)


class HttpDelovyeLiniiProvider:
    """Real Деловые Линии API integration.

    Requires env vars: DL_API_KEY.
    Uses DL API (https://www.dellin.ru/api/).
    """
    name = "http_delovye_linii"

    def __init__(self) -> None:
        from app.core.config import settings
        self.api_key = getattr(settings, "DL_API_KEY", "")
        self.base_url = getattr(settings, "DL_API_URL", "") or "https://www.dellin.ru/api"

    def health(self) -> Dict[str, Any]:
        configured = bool(self.api_key)
        return {"status": "ok" if configured else "degraded", "provider": self.name, "configured": configured}

    def estimate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from app.core.logging import get_logger
        logger = get_logger(__name__)

        if not self.api_key:
            return MockDelovyeLiniiProvider().estimate(payload)

        try:
            import httpx

            calc_body = {
                "appkey": self.api_key,
                "derivalPoint": payload.get("from_city", "Москва"),
                "arrivalPoint": payload.get("to_city", "Санкт-Петербург"),
                "weight": payload.get("weight", 1000) / 1000,
                "volume": payload.get("volume", 0.1),
                "quantity": payload.get("quantity", 1),
            }

            resp = httpx.post(
                f"{self.base_url}/public/calculator.json",
                json=calc_body,
                headers={"Content-Type": "application/json"},
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()

            price = data.get("price") or data.get("totalPrice") or data.get("intercity", {}).get("price", 690)
            days = data.get("time", {}).get("exact") or data.get("time", {}).get("nominal")

            return {
                "provider": "delovye_linii",
                "price": price,
                "days": days,
                "currency": "RUB",
                "delivery_type": payload.get("delivery_type", "terminal"),
            }
        except Exception as exc:
            logger.warning("dl_estimate_failed", extra={"extra": {"error": str(exc)}})
            return MockDelovyeLiniiProvider().estimate(payload)


class MockCatalogProvider:
    name = "mock_catalog"

    def health(self) -> Dict[str, Any]:
        return {"status": "ok", "provider": self.name}

    def decode_vin(self, vin: str) -> Dict[str, Any]:
        return {"vin": vin, "brand": "KAMAZ", "model": "5490", "year": 2022}


class MockEmailProvider:
    name = "mock_email"

    def health(self) -> Dict[str, Any]:
        return {"status": "ok", "provider": self.name}

    def send(self, to: str, message: str) -> Dict[str, Any]:
        return {"provider": self.name, "channel": "email", "to": to, "message": message, "status": "queued"}


class MockSmsProvider:
    name = "mock_sms"

    def health(self) -> Dict[str, Any]:
        return {"status": "ok", "provider": self.name}

    def send(self, to: str, message: str) -> Dict[str, Any]:
        return {"provider": self.name, "channel": "sms", "to": to, "message": message, "status": "queued"}


class MockTelegramProvider:
    name = "mock_telegram"

    def health(self) -> Dict[str, Any]:
        return {"status": "ok", "provider": self.name}

    def send(self, to: str, message: str) -> Dict[str, Any]:
        return {"provider": self.name, "channel": "telegram", "to": to, "message": message, "status": "queued"}


class HttpEmailProvider:
    """Real SMTP email provider using app config (SMTP_HOST, SMTP_PORT, etc.)."""
    name = "http_email"

    def __init__(self) -> None:
        from app.core.config import settings
        self.smtp_host = getattr(settings, "SMTP_HOST", "")
        self.smtp_port = getattr(settings, "SMTP_PORT", 587)
        self.smtp_user = getattr(settings, "SMTP_USER", "")
        self.smtp_password = getattr(settings, "SMTP_PASSWORD", "")

    def health(self) -> Dict[str, Any]:
        configured = bool(self.smtp_host and self.smtp_user)
        return {"status": "ok" if configured else "degraded", "provider": self.name, "configured": configured}

    def send(self, to: str, message: str) -> Dict[str, Any]:
        from app.core.logging import get_logger
        logger = get_logger(__name__)

        if not self.smtp_host or not self.smtp_user:
            return MockEmailProvider().send(to, message)

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            from app.core.config import settings

            msg = MIMEMultipart()
            msg["From"] = self.smtp_user
            msg["To"] = to
            msg["Subject"] = f"{settings.PROJECT_NAME} — уведомление"
            msg.attach(MIMEText(message, "html", "utf-8"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            return {"provider": self.name, "channel": "email", "to": to, "status": "sent"}
        except Exception as exc:
            logger.warning("email_send_failed", extra={"extra": {"to": to, "error": str(exc)}})
            return {"provider": self.name, "channel": "email", "to": to, "status": "failed", "error": str(exc)}


class HttpSmsProvider:
    """Real SMS provider. Supports generic SMS API with configurable endpoint.

    Requires env vars: SMS_API_URL, SMS_API_KEY.
    """
    name = "http_sms"

    def __init__(self) -> None:
        from app.core.config import settings
        self.api_url = getattr(settings, "SMS_API_URL", "")
        self.api_key = getattr(settings, "SMS_API_KEY", "")

    def health(self) -> Dict[str, Any]:
        configured = bool(self.api_url and self.api_key)
        return {"status": "ok" if configured else "degraded", "provider": self.name, "configured": configured}

    def send(self, to: str, message: str) -> Dict[str, Any]:
        from app.core.logging import get_logger
        logger = get_logger(__name__)

        if not self.api_url or not self.api_key:
            return MockSmsProvider().send(to, message)

        try:
            import httpx

            resp = httpx.post(
                self.api_url,
                json={"to": to, "message": message, "api_key": self.api_key},
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                timeout=10.0,
            )
            resp.raise_for_status()

            return {"provider": self.name, "channel": "sms", "to": to, "status": "sent"}
        except Exception as exc:
            logger.warning("sms_send_failed", extra={"extra": {"to": to, "error": str(exc)}})
            return {"provider": self.name, "channel": "sms", "to": to, "status": "failed", "error": str(exc)}


class HttpTelegramProvider:
    """Real Telegram Bot API provider.

    Requires env var: TELEGRAM_BOT_TOKEN.
    """
    name = "http_telegram"

    def __init__(self) -> None:
        from app.core.config import settings
        self.bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")

    def health(self) -> Dict[str, Any]:
        configured = bool(self.bot_token)
        return {"status": "ok" if configured else "degraded", "provider": self.name, "configured": configured}

    def send(self, to: str, message: str) -> Dict[str, Any]:
        from app.core.logging import get_logger
        logger = get_logger(__name__)

        if not self.bot_token:
            return MockTelegramProvider().send(to, message)

        try:
            import httpx

            chat_id = to
            if not to.lstrip("-").isdigit():
                chat_id = to

            resp = httpx.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("ok"):
                return {"provider": self.name, "channel": "telegram", "to": to, "status": "sent", "message_id": data.get("result", {}).get("message_id")}
            else:
                return {"provider": self.name, "channel": "telegram", "to": to, "status": "failed", "error": data.get("description", "unknown")}
        except Exception as exc:
            logger.warning("telegram_send_failed", extra={"extra": {"to": to, "error": str(exc)}})
            return {"provider": self.name, "channel": "telegram", "to": to, "status": "failed", "error": str(exc)}


class MockErpProvider:
    name = "mock_erp"

    def health(self) -> Dict[str, Any]:
        return {"status": "ok", "provider": self.name}
