from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MessageCategory(StrEnum):
    GREETING = "greeting"
    CRYPTO_QUESTION = "crypto_question"
    POST_EXPLANATION = "post_explanation"
    GENERAL_SUPPORT = "general_support"
    COMPLAINT = "complaint"
    ABUSE = "abuse_or_harassment"
    SPAM = "spam"
    SCAM = "scam"
    PROMOTION = "promotion_offer"
    PARTNERSHIP = "partnership_request"
    PRESS = "press_or_media"
    LEGAL = "legal_request"
    SECURITY = "account_security"
    HUMAN_REQUIRED = "human_required"


class InboundMessage(BaseModel):
    platform: str
    sender_id: str
    message_id: str
    text: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class MessageDecision(BaseModel):
    category: MessageCategory
    confidence: float = Field(ge=0, le=1)
    risk: str = "low"
    requires_owner: bool = False
    reason: str = ""


class PromotionAssessment(BaseModel):
    brand_name: str | None = None
    official_website: str | None = None
    contact_email: str | None = None
    budget: str | None = None
    deliverables: str | None = None
    identity_score: int = Field(default=0, ge=0, le=100)
    brand_safety_score: int = Field(default=0, ge=0, le=100)
    scam_probability: int = Field(default=0, ge=0, le=100)
    missing_fields: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    recommendation: str = "request_information"


class ReplyPlan(BaseModel):
    reply_text: str
    category: MessageCategory
    requires_owner: bool = False
    promotion: PromotionAssessment | None = None
    should_send: bool = True
