from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class DeliveryEstimateRequest:
    provider: str
    from_city: str
    to_city: str
    weight_kg: float
    volume_m3: float
    delivery_type: str = "courier"


def validate_delivery_payload(payload: Dict[str, Any]) -> DeliveryEstimateRequest:
    provider = (payload.get("provider") or "cdek").lower().strip()
    from_city = (payload.get("from_city") or "").strip()
    to_city = (payload.get("to_city") or "").strip()
    delivery_type = (payload.get("delivery_type") or "courier").strip()

    try:
        weight_kg = float(payload.get("weight_kg", 0))
        volume_m3 = float(payload.get("volume_m3", 0))
    except Exception as exc:
        raise ValueError("weight_kg and volume_m3 must be numbers") from exc

    if provider not in ("cdek", "pec", "delovye_linii"):
        raise ValueError("unsupported provider")
    if not from_city or not to_city:
        raise ValueError("from_city and to_city are required")
    if weight_kg <= 0 or volume_m3 < 0:
        raise ValueError("invalid weight/volume")

    return DeliveryEstimateRequest(
        provider=provider,
        from_city=from_city,
        to_city=to_city,
        weight_kg=weight_kg,
        volume_m3=volume_m3,
        delivery_type=delivery_type,
    )


def normalize_delivery_response(*, provider: str, price: float, days: int, currency: str = "RUB", delivery_type: str = "courier") -> Dict[str, Any]:
    return {
        "provider": provider,
        "delivery_type": delivery_type,
        "price": round(float(price), 2),
        "days": int(days),
        "currency": currency,
    }
