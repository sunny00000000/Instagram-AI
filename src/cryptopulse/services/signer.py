from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path
from urllib.parse import quote

from cryptopulse.config import Settings


class MediaURLSigner:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.secret = settings.media_signing_secret.encode("utf-8")

    def sign_path(self, relative_path: str, expires_at: int | None = None) -> str:
        if not self.settings.public_base_url:
            raise ValueError("PUBLIC_BASE_URL is required to create public media URLs")
        expires = expires_at or int(time.time()) + self.settings.media_url_ttl_seconds
        normalized = Path(relative_path).as_posix().lstrip("/")
        signature = hmac.new(
            self.secret, f"{normalized}:{expires}".encode(), hashlib.sha256
        ).hexdigest()
        encoded = "/".join(quote(part) for part in normalized.split("/"))
        return f"{self.settings.public_base_url}/media/{encoded}?exp={expires}&sig={signature}"

    def verify(self, relative_path: str, expires_at: int, signature: str) -> bool:
        if expires_at < int(time.time()):
            return False
        normalized = Path(relative_path).as_posix().lstrip("/")
        expected = hmac.new(
            self.secret, f"{normalized}:{expires_at}".encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
