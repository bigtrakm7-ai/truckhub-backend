"""Chat moderation — anti-disintermediation rules.

Prevents users from sharing direct contact info (phone, email, website)
that could bypass the platform. Violations are flagged and logged.
"""

import re
from typing import Dict, Any, List, Tuple
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Patterns ─────────────────────────────────────────────────────────

PHONE_PATTERNS = [
    re.compile(r"\+7[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}", re.IGNORECASE),
    re.compile(r"8[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"),
    re.compile(r"\b\d{1}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b"),
]

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

WEBSITE_PATTERNS = [
    re.compile(r"https?://[^\s]+", re.IGNORECASE),
    re.compile(r"www\.[^\s]+", re.IGNORECASE),
    re.compile(r"\b[a-z0-9-]+\.(ru|com|net|org|io|рф)\b", re.IGNORECASE),
]

SOCIAL_PATTERNS = [
    re.compile(r"telegram\.me/[^\s]+", re.IGNORECASE),
    re.compile(r"t\.me/[^\s]+", re.IGNORECASE),
    re.compile(r"wa\.me/[^\s]+", re.IGNORECASE),
    re.compile(r"whatsapp[^\s]*[:\s]\+?\d+", re.IGNORECASE),
    re.compile(r"вконтакте\.ru/[^\s]+", re.IGNORECASE),
    re.compile(r"vk\.com/[^\s]+", re.IGNORECASE),
]

SKYPE_PATTERN = re.compile(r"skype[:\s][^\s]+", re.IGNORECASE)

# ── Obfuscation detection ────────────────────────────────────────────

OBFUSCATION_HINTS = [
    re.compile(r"(\+\s*7|семь|восемь)", re.IGNORECASE),
    re.compile(r"(собака|собачка|at|эт)\s*", re.IGNORECASE),
    re.compile(r"(точка|dot)\s*", re.IGNORECASE),
    re.compile(r"(ноль|один|два|три|четыре|пять|шесть|семь|восемь|девять)", re.IGNORECASE),
]


class ModerationResult:
    def __init__(self, is_clean: bool, violations: List[Dict[str, Any]], sanitized_content: str):
        self.is_clean = is_clean
        self.violations = violations
        self.sanitized_content = sanitized_content

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_clean": self.is_clean,
            "violations": self.violations,
            "sanitized_content": self.sanitized_content,
        }


def moderate_message(content: str) -> ModerationResult:
    """Check a chat message for disintermediation violations."""
    violations = []
    sanitized = content

    # Check phones
    for pattern in PHONE_PATTERNS:
        matches = pattern.findall(content)
        for match in matches:
            violations.append({"type": "phone", "value": match, "rule": "contact_sharing"})
            sanitized = pattern.sub("[ТЕЛЕФОН УДАЛЁН]", sanitized)

    # Check emails
    email_matches = EMAIL_PATTERN.findall(content)
    for match in email_matches:
        violations.append({"type": "email", "value": match, "rule": "contact_sharing"})
        sanitized = EMAIL_PATTERN.sub("[EMAIL УДАЛЁН]", sanitized)

    # Check websites
    for pattern in WEBSITE_PATTERNS:
        matches = pattern.findall(content)
        for match in matches:
            violations.append({"type": "website", "value": match, "rule": "contact_sharing"})
            sanitized = pattern.sub("[САЙТ УДАЛЁН]", sanitized)

    # Check social media
    for pattern in SOCIAL_PATTERNS:
        matches = pattern.findall(content)
        for match in matches:
            violations.append({"type": "social", "value": match, "rule": "contact_sharing"})
            sanitized = pattern.sub("[ССЫЛКА УДАЛЕНА]", sanitized)

    # Check Skype
    skype_matches = SKYPE_PATTERN.findall(content)
    for match in skype_matches:
        violations.append({"type": "skype", "value": match, "rule": "contact_sharing"})
        sanitized = SKYPE_PATTERN.sub("[SKYPE УДАЛЁН]", sanitized)

    # Check obfuscation hints
    obfuscation_found = []
    for pattern in OBFUSCATION_HINTS:
        if pattern.search(content):
            obfuscation_found.append(pattern.pattern)
    if obfuscation_found and not violations:
        violations.append({
            "type": "obfuscation_suspected",
            "value": "Possible contact info obfuscation detected",
            "rule": "anti_obfuscation",
        })

    is_clean = len(violations) == 0

    if not is_clean:
        logger.warning("chat_moderation_violation", extra={
            "extra": {
                "violations": [v["type"] for v in violations],
                "original_length": len(content),
            }
        })

    return ModerationResult(
        is_clean=is_clean,
        violations=violations,
        sanitized_content=sanitized,
    )
