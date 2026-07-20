from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx

from cryptopulse.config import Settings
from cryptopulse.schemas_messaging import InboundMessage


class MetaMessagingClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=30)
        self.base_url = f"https://graph.facebook.com/{settings.meta_graph_version}"

    async def close(self) -> None:
        await self.client.aclose()

    def verify_signature(self, body: bytes, signature: str | None) -> bool:
        if not self.settings.meta_app_secret:
            return self.settings.dry_run
        if not signature or not signature.startswith("sha256="):
            return False
        expected = hmac.new(self.settings.meta_app_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature.removeprefix("sha256="), expected)

    def parse_events(self, payload: dict[str, Any]) -> list[InboundMessage]:
        output: list[InboundMessage] = []
        for entry in payload.get("entry", []):
            for event in entry.get("messaging", []):
                message = event.get("message") or {}
                if not message or message.get("is_echo"):
                    continue
                sender = str((event.get("sender") or {}).get("id") or "")
                mid = str(message.get("mid") or f"{entry.get('id','')}-{event.get('timestamp','')}")
                if not sender:
                    continue
                output.append(InboundMessage(platform=str(payload.get("object") or "meta"), sender_id=sender, message_id=mid, text=str(message.get("text") or ""), attachments=list(message.get("attachments") or []), raw=event))
        return output

    async def send_text(self, recipient_id: str, text: str) -> dict[str, Any]:
        if self.settings.dry_run:
            return {"recipient_id": recipient_id, "message_id": "dry-run-message"}
        response = await self.client.post(
            f"{self.base_url}/me/messages",
            params={"access_token": self.settings.meta_access_token},
            json={"recipient": {"id": recipient_id}, "message": {"text": text}},
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result
