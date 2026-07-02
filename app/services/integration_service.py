from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.services.providers import (
    MockPaymentProvider,
    MockCdekProvider,
    MockPecProvider,
    MockDelovyeLiniiProvider,
    HttpCdekProvider,
    HttpPecProvider,
    HttpDelovyeLiniiProvider,
    MockCatalogProvider,
    MockEmailProvider,
    MockSmsProvider,
    MockTelegramProvider,
    HttpEmailProvider,
    HttpSmsProvider,
    HttpTelegramProvider,
    MockErpProvider,
)
from app.services.vin_provider import MockLaximoProvider, HttpLaximoProvider
from app.services.notification_schema import (
    NotificationPayload,
    validate_notification_payload,
    safe_notification_result,
)
from app.core.messages import Msg
from app.services.delivery_schema import (
    DeliveryEstimateRequest,
    validate_delivery_payload,
    normalize_delivery_response,
)


class IntegrationService:
    def __init__(self) -> None:
        self.payment = MockPaymentProvider()

        if settings.PROVIDER_MODE == "http":
            self.cdek_provider = HttpCdekProvider()
            self.pec_provider = HttpPecProvider()
            self.dl_provider = HttpDelovyeLiniiProvider()
            self.email_provider = HttpEmailProvider()
            self.sms_provider = HttpSmsProvider()
            self.telegram_provider = HttpTelegramProvider()
            self.vin_provider = HttpLaximoProvider()
        else:
            self.cdek_provider = MockCdekProvider()
            self.pec_provider = MockPecProvider()
            self.dl_provider = MockDelovyeLiniiProvider()
            self.email_provider = MockEmailProvider()
            self.sms_provider = MockSmsProvider()
            self.telegram_provider = MockTelegramProvider()
            self.vin_provider = MockLaximoProvider()

        self.catalog = MockCatalogProvider()
        self.erp = MockErpProvider()

    def providers_health(self) -> Dict[str, Any]:
        return {
            "payment": self.payment.health(),
            "cdek": self.cdek_provider.health(),
            "pec": self.pec_provider.health(),
            "delovye_linii": self.dl_provider.health(),
            "catalog": self.catalog.health(),
            "email": self.email_provider.health(),
            "sms": self.sms_provider.health(),
            "telegram": self.telegram_provider.health(),
            "erp": self.erp.health(),
            "vin_decoder": self.vin_provider.health(),
        }

    def _dispatch_delivery(self, req: DeliveryEstimateRequest) -> Dict[str, Any]:
        payload = {
            "from_city": req.from_city,
            "to_city": req.to_city,
            "weight_kg": req.weight_kg,
            "volume_m3": req.volume_m3,
            "delivery_type": req.delivery_type,
        }
        if req.provider == "cdek":
            raw = self.cdek_provider.estimate(payload)
        elif req.provider == "pec":
            raw = self.pec_provider.estimate(payload)
        elif req.provider == "delovye_linii":
            raw = self.dl_provider.estimate(payload)
        else:
            raise ValueError(Msg.UNSUPPORTED_PROVIDER)

        return normalize_delivery_response(
            provider=raw.get("provider", req.provider),
            price=raw.get("price", 0),
            days=raw.get("days", 0),
            currency=raw.get("currency", "RUB"),
            delivery_type=raw.get("delivery_type", req.delivery_type),
        )

    def estimate_delivery(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        req = validate_delivery_payload(payload)
        return self._dispatch_delivery(req)

    def decode_vin(self, vin: str) -> Dict[str, Any]:
        return self.vin_provider.decode_vin(vin)

    def get_vehicle_tree(self, vin: str) -> List[Dict[str, Any]]:
        return self.vin_provider.get_vehicle_tree(vin)

    def _dispatch_notification(self, p: NotificationPayload) -> Dict[str, Any]:
        if p.channel == "email":
            return self.email_provider.send(to=p.to, message=p.message)
        if p.channel == "sms":
            return self.sms_provider.send(to=p.to, message=p.message)
        if p.channel == "telegram":
            return self.telegram_provider.send(to=p.to, message=p.message)
        raise ValueError(Msg.UNSUPPORTED_CHANNEL)

    def send_notification(self, channel: str, to: str, message: str) -> Dict[str, Any]:
        try:
            payload = validate_notification_payload({"channel": channel, "to": to, "message": message})
            return self._dispatch_notification(payload)
        except Exception as exc:
            return safe_notification_result(
                channel=channel,
                to=to,
                status="failed",
                provider="router",
                error=str(exc),
            )

    def notify_order_status_changed(self, *, user_email: Optional[str], order_number: str, status: str) -> Dict[str, Any]:
        recipient = user_email or ""
        msg = Msg.order_status_changed(order_number, status)
        return self.send_notification(channel="email", to=recipient, message=msg)

    def notify_return_status_changed(self, *, user_email: Optional[str], return_id: str, status: str) -> Dict[str, Any]:
        recipient = user_email or ""
        msg = Msg.return_status_changed(return_id, status)
        return self.send_notification(channel="email", to=recipient, message=msg)

    def notify_with_preferences(
        self,
        *,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        email_enabled: bool = True,
        sms_enabled: bool = False,
        telegram_enabled: bool = False,
        message: str,
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {}

        if email_enabled and email:
            results["email"] = self.send_notification(channel="email", to=email, message=message)

        if sms_enabled and phone:
            results["sms"] = self.send_notification(channel="sms", to=phone, message=message)

        if telegram_enabled and telegram_chat_id:
            results["telegram"] = self.send_notification(
                channel="telegram",
                to=telegram_chat_id,
                message=message,
            )

        if not results:
            results["skipped"] = {
                "status": "skipped",
                "reason": "нет_включённых_каналов_или_контактов",
            }

        return results


integration_service = IntegrationService()
