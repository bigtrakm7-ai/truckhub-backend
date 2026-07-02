from dataclasses import dataclass
from typing import Optional, Literal, Dict, Any

from app.core.messages import Msg


NotificationChannel = Literal["email", "sms", "telegram"]


@dataclass
class NotificationPayload:
    channel: NotificationChannel
    to: str
    message: str


def validate_notification_payload(payload: Dict[str, Any]) -> NotificationPayload:
    channel = payload.get("channel", "email")
    to = (payload.get("to") or "").strip()
    message = (payload.get("message") or "").strip()

    if channel not in ("email", "sms", "telegram"):
        raise ValueError(Msg.UNSUPPORTED_CHANNEL)
    if not to:
        raise ValueError(Msg.RECIPIENT_REQUIRED)
    if not message:
        raise ValueError(Msg.MESSAGE_REQUIRED)

    return NotificationPayload(channel=channel, to=to, message=message)


def safe_notification_result(*, channel: str, to: str, status: str, provider: str, error: Optional[str] = None) -> Dict[str, Any]:
    result = {
        "channel": channel,
        "to": to,
        "status": status,
        "provider": provider,
    }
    if error:
        result["error"] = error
    return result
