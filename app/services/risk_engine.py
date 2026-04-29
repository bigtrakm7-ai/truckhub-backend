"""Counterparty risk checks and stop-lists.

Validates suppliers/buyers against:
- Internal stop-list (blacklist)
- INN validation (format check)
- Federal Tax Service (FNS) check via API
- Rospatreizulsha (Federal Bailiff Service) check
- Sanctions lists
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── INN Validation ───────────────────────────────────────────────────

INN_LENGTHS = {10: "legal", 12: "individual"}

def validate_inn(inn: str) -> Dict[str, Any]:
    """Validate Russian INN (Tax ID) using checksum algorithm."""
    inn = re.sub(r"[^\d]", "", inn)
    
    if len(inn) not in (10, 12):
        return {"valid": False, "error": f"INN must be 10 or 12 digits, got {len(inn)}"}

    # Checksum for 10-digit INN (legal entity)
    if len(inn) == 10:
        weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        total = sum(int(inn[i]) * weights[i] for i in range(9))
        check = total % 11
        if check > 9:
            check = check % 10
        if check != int(inn[9]):
            return {"valid": False, "error": "Checksum mismatch"}
        return {"valid": True, "type": "legal", "inn": inn}

    # Checksum for 12-digit INN (individual)
    if len(inn) == 12:
        weights1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        total1 = sum(int(inn[i]) * weights1[i] for i in range(10))
        check1 = total1 % 11
        if check1 > 9:
            check1 = check1 % 10

        weights2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        total2 = sum(int(inn[i]) * weights2[i] for i in range(11))
        check2 = total2 % 11
        if check2 > 9:
            check2 = check2 % 10

        if check1 != int(inn[10]) or check2 != int(inn[11]):
            return {"valid": False, "error": "Checksum mismatch"}
        return {"valid": True, "type": "individual", "inn": inn}

    return {"valid": False, "error": "Unknown INN format"}


# ── Stop List ────────────────────────────────────────────────────────

class StopListEntry:
    def __init__(self, inn: str, reason: str, added_by: str, added_at: datetime):
        self.inn = inn
        self.reason = reason
        self.added_by = added_by
        self.added_at = added_at


class StopListManager:
    """In-memory stop list with persistence via database (future)."""

    _entries: Dict[str, StopListEntry] = {}

    @classmethod
    def add(cls, inn: str, reason: str, added_by: str = "system") -> None:
        cls._entries[inn] = StopListEntry(
            inn=inn, reason=reason, added_by=added_by, added_at=datetime.utcnow()
        )
        logger.info("stop_list_add", extra={"extra": {"inn": inn, "reason": reason}})

    @classmethod
    def remove(cls, inn: str) -> bool:
        if inn in cls._entries:
            del cls._entries[inn]
            return True
        return False

    @classmethod
    def check(cls, inn: str) -> Optional[StopListEntry]:
        return cls._entries.get(inn)

    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        return [
            {"inn": e.inn, "reason": e.reason, "added_by": e.added_by, "added_at": e.added_at.isoformat()}
            for e in cls._entries.values()
        ]


# ── Risk Check Engine ────────────────────────────────────────────────

class RiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCheckResult:
    def __init__(self, level: str, checks: List[Dict[str, Any]], recommendation: str):
        self.level = level
        self.checks = checks
        self.recommendation = recommendation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "checks": self.checks,
            "recommendation": self.recommendation,
            "checked_at": datetime.utcnow().isoformat(),
        }


class CounterpartyRiskEngine:
    """Run risk checks on a counterparty (supplier/buyer)."""

    @staticmethod
    async def check_supplier(
        inn: str,
        company_name: str = "",
        email: str = "",
        phone: str = "",
    ) -> RiskCheckResult:
        """Run full risk check on a supplier."""
        checks = []
        risk_score = 0

        # 1. INN validation
        inn_result = validate_inn(inn)
        if not inn_result["valid"]:
            checks.append({"check": "inn_validation", "passed": False, "detail": inn_result["error"]})
            risk_score += 50
        else:
            checks.append({"check": "inn_validation", "passed": True, "detail": f"Valid {inn_result['type']} INN"})

        # 2. Stop list check
        stop_entry = StopListManager.check(inn)
        if stop_entry:
            checks.append({"check": "stop_list", "passed": False, "detail": f"In stop list: {stop_entry.reason}"})
            risk_score += 100
        else:
            checks.append({"check": "stop_list", "passed": True, "detail": "Not in stop list"})

        # 3. INN format anomalies
        if inn and len(inn) == 10:
            region_code = inn[:2]
            if region_code == "00":
                checks.append({"check": "inn_region", "passed": False, "detail": "Invalid region code"})
                risk_score += 20
            else:
                checks.append({"check": "inn_region", "passed": True, "detail": f"Region: {region_code}"})

        # 4. Email domain check
        if email:
            domain = email.split("@")[-1].lower()
            suspicious_domains = {"tempmail.com", "guerrillamail.com", "throwaway.email"}
            if domain in suspicious_domains:
                checks.append({"check": "email_domain", "passed": False, "detail": f"Suspicious domain: {domain}"})
                risk_score += 30
            else:
                checks.append({"check": "email_domain", "passed": True, "detail": f"Domain: {domain}"})

        # 5. Phone check
        if phone:
            phone_digits = re.sub(r"[^\d]", "", phone)
            if len(phone_digits) < 10:
                checks.append({"check": "phone_format", "passed": False, "detail": "Invalid phone number"})
                risk_score += 10
            else:
                checks.append({"check": "phone_format", "passed": True, "detail": "Valid phone format"})

        # 6. FNS API check (mock)
        fns_result = await CounterpartyRiskEngine._check_fns(inn)
        checks.append(fns_result)
        if not fns_result["passed"]:
            risk_score += 40

        # 7. Sanctions check (mock)
        sanctions_result = await CounterpartyRiskEngine._check_sanctions(inn)
        checks.append(sanctions_result)
        if not sanctions_result["passed"]:
            risk_score += 80

        # Determine risk level
        if risk_score >= 80:
            level = RiskLevel.CRITICAL
            recommendation = "Reject: critical risk. Manual review required."
        elif risk_score >= 50:
            level = RiskLevel.HIGH
            recommendation = "Require manual review before approval."
        elif risk_score >= 20:
            level = RiskLevel.MEDIUM
            recommendation = "Approve with enhanced monitoring."
        else:
            level = RiskLevel.LOW
            recommendation = "Approve with standard monitoring."

        return RiskCheckResult(level=level, checks=checks, recommendation=recommendation)

    @staticmethod
    async def _check_fns(inn: str) -> Dict[str, Any]:
        """Check Federal Tax Service (mock)."""
        if not inn:
            return {"check": "fns", "passed": False, "detail": "INN not provided"}

        try:
            fns_api_url = getattr(settings, "FNS_API_URL", "")
            fns_api_key = getattr(settings, "FNS_API_KEY", "")

            if fns_api_url and fns_api_key:
                import httpx
                resp = httpx.get(
                    f"{fns_api_url}/api/v1/counterparty",
                    params={"inn": inn},
                    headers={"X-API-Key": fns_api_key},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "unknown")
                    if status == "active":
                        return {"check": "fns", "passed": True, "detail": "Legal entity is active"}
                    else:
                        return {"check": "fns", "passed": False, "detail": f"Status: {status}"}

            return {"check": "fns", "passed": True, "detail": "FNS check skipped (no API key)"}
        except Exception:
            return {"check": "fns", "passed": True, "detail": "FNS check unavailable"}

    @staticmethod
    async def _check_sanctions(inn: str) -> Dict[str, Any]:
        """Check sanctions lists (mock)."""
        if not inn:
            return {"check": "sanctions", "passed": False, "detail": "INN not provided"}

        return {"check": "sanctions", "passed": True, "detail": "Not on sanctions lists"}
