from __future__ import annotations

import re
from dataclasses import dataclass

_SENSITIVE_PATH = re.compile(r"(?:^|/)(?:\.env(?:\..*)?|id_[a-z]+|.*\.(?:pem|key|p12|pfx))$", re.I)
_SECRET = re.compile(
    r"(?P<name>api[_-]?key|token|secret|password|authorization)\s*[:=]\s*[\"']?(?P<value>[A-Za-z0-9_\-/.+=]{12,})",
    re.I,
)
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----", re.I)


@dataclass(frozen=True)
class SecretScan:
    detected: bool
    redacted_text: str
    matches: tuple[str, ...]


def is_sensitive_path(path: str) -> bool:
    return bool(_SENSITIVE_PATH.search(path.replace("\\", "/")))


def scan_and_redact(text: str) -> SecretScan:
    matches = tuple(match.group("name").lower() for match in _SECRET.finditer(text))
    has_private_key = bool(_PRIVATE_KEY.search(text))
    redacted = _SECRET.sub(lambda item: f"{item.group('name')}=[REDACTED_SECRET]", text)
    redacted = _PRIVATE_KEY.sub("[REDACTED_PRIVATE_KEY]", redacted)
    return SecretScan(
        detected=bool(matches) or has_private_key,
        redacted_text=redacted,
        matches=matches + (("private_key",) if has_private_key else ()),
    )
