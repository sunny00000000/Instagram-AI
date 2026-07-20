from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from cryptopulse.api import app
from cryptopulse.config import Settings
from cryptopulse.providers.meta_messaging import MetaMessagingClient
from cryptopulse.schemas_messaging import InboundMessage, MessageCategory
from cryptopulse.services.messaging import ConversationService
from cryptopulse.services.promotion import assess_promotion


def test_normal_user_greeting() -> None:
    service = ConversationService(Settings(brand_name="CryptoPulse AI"))
    plan = __import__('asyncio').run(service.plan_reply(InboundMessage(platform="instagram", sender_id="1", message_id="m1", text="Hi there")))
    assert plan.category == MessageCategory.GREETING
    assert "AI-assisted" in plan.reply_text


def test_crypto_question_is_not_financial_advice() -> None:
    service = ConversationService(Settings())
    plan = __import__('asyncio').run(service.plan_reply(InboundMessage(platform="instagram", sender_id="1", message_id="m2", text="Will bitcoin go up?")))
    assert plan.category == MessageCategory.CRYPTO_QUESTION
    assert "cannot guarantee" in plan.reply_text


def test_legitimate_promotion_requests_missing_information() -> None:
    assessment = assess_promotion("We want a paid post for Example Brand. Budget $500. https://example.com contact@example.com")
    assert assessment.recommendation == "request_information"
    assert "contract and usage rights" in assessment.missing_fields


def test_complete_promotion_requires_owner() -> None:
    text = "Partnership from Example Brand https://example.com contact@example.com. Budget $500. One Reel deliverable, campaign date August 10, contract and usage rights included."
    service = ConversationService(Settings())
    plan = __import__('asyncio').run(service.plan_reply(InboundMessage(platform="instagram", sender_id="2", message_id="m3", text=text)))
    assert plan.requires_owner is True
    assert plan.promotion is not None
    assert plan.promotion.recommendation == "owner_review"
    assert "final owner review" in plan.reply_text


def test_scam_auto_rejected() -> None:
    service = ConversationService(Settings())
    plan = __import__('asyncio').run(service.plan_reply(InboundMessage(platform="instagram", sender_id="3", message_id="m4", text="Send your seed phrase and a verification fee for guaranteed profit")))
    assert plan.category == MessageCategory.SCAM
    assert "declined" in plan.reply_text


def test_webhook_signature() -> None:
    settings = Settings(meta_app_secret="secret", dry_run=False)
    client = MetaMessagingClient(settings)
    body = b'{"object":"instagram","entry":[]}'
    sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert client.verify_signature(body, sig)
    assert not client.verify_signature(body, "sha256=bad")
    __import__('asyncio').run(client.close())


def test_event_parser_ignores_echo() -> None:
    client = MetaMessagingClient(Settings())
    payload = {"object":"instagram", "entry":[{"id":"p", "messaging":[
        {"sender":{"id":"u1"}, "timestamp":1, "message":{"mid":"a", "text":"hello"}},
        {"sender":{"id":"page"}, "timestamp":2, "message":{"mid":"b", "text":"echo", "is_echo":True}},
    ]}]}
    events = client.parse_events(payload)
    assert len(events) == 1
    assert events[0].message_id == "a"
    __import__('asyncio').run(client.close())


def test_webhook_verification_and_processing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("META_WEBHOOK_VERIFY_TOKEN", "verify-me")
    monkeypatch.setenv("META_APP_SECRET", "secret")
    monkeypatch.setenv("AUTO_REPLY_ENABLED", "true")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/messages.db")
    from cryptopulse.config import get_settings
    get_settings.cache_clear()
    # api module settings were created at import time, so set directly for the verification route
    import cryptopulse.api as api_module
    api_module.settings.meta_webhook_verify_token = "verify-me"
    with TestClient(app) as client:
        response = client.get("/webhooks/meta?hub.mode=subscribe&hub.verify_token=verify-me&hub.challenge=12345")
        assert response.status_code == 200 and response.text == "12345"
        payload = {"object":"instagram", "entry":[{"id":"p", "messaging":[{"sender":{"id":"u1"}, "timestamp":1, "message":{"mid":"msg-real-1", "text":"hello"}}]}]}
        body = json.dumps(payload).encode()
        sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        response = client.post("/webhooks/meta", content=body, headers={"x-hub-signature-256":sig, "content-type":"application/json"})
        assert response.status_code == 200
        assert response.json()["events"] == 1
