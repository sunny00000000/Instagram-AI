from __future__ import annotations

import re

from cryptopulse.config import Settings
from cryptopulse.schemas_messaging import (
    InboundMessage,
    MessageCategory,
    MessageDecision,
    ReplyPlan,
)
from cryptopulse.services.promotion import assess_promotion

PROMO_TERMS = ("sponsor", "promotion", "paid post", "advertising", "collaboration", "partnership", "brand ambassador", "affiliate")
SCAM_TERMS = ("seed phrase", "private key", "send otp", "verification fee", "guaranteed profit", "gift card")


class ConversationService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def classify(self, message: InboundMessage) -> MessageDecision:
        text = message.text.strip().lower()
        if any(term in text for term in SCAM_TERMS):
            return MessageDecision(category=MessageCategory.SCAM, confidence=.99, risk="high", requires_owner=False, reason="Credential/payment scam indicators")
        if any(term in text for term in PROMO_TERMS):
            return MessageDecision(category=MessageCategory.PROMOTION, confidence=.94, risk="medium", requires_owner=True, reason="Commercial proposal indicators")
        if re.search(r"\b(hi|hello|hey|good morning|good evening)\b", text):
            return MessageDecision(category=MessageCategory.GREETING, confidence=.9, reason="Greeting")
        if any(term in text for term in ("bitcoin", "ethereum", "crypto", "coin", "bullish", "bearish")):
            return MessageDecision(category=MessageCategory.CRYPTO_QUESTION, confidence=.85, risk="medium", reason="Crypto-related question")
        if any(term in text for term in ("complaint", "wrong", "misleading", "refund")):
            return MessageDecision(category=MessageCategory.COMPLAINT, confidence=.8, requires_owner=True, reason="Complaint")
        return MessageDecision(category=MessageCategory.GENERAL_SUPPORT, confidence=.65, reason="General conversation")

    async def plan_reply(self, message: InboundMessage) -> ReplyPlan:
        decision = self.classify(message)
        if decision.category == MessageCategory.SCAM:
            return ReplyPlan(reply_text="For security, we cannot help with passwords, OTPs, private keys, seed phrases, advance fees, or guaranteed-return offers. This conversation has been declined.", category=decision.category)
        if decision.category == MessageCategory.PROMOTION:
            assessment = assess_promotion(message.text)
            if assessment.recommendation == "reject":
                reply = "Thank you for contacting us. We cannot proceed because the proposal does not meet our authenticity, security, or brand-safety requirements."
            elif assessment.recommendation == "request_information":
                reply = "Thank you for the partnership enquiry. For verification, please send the official company name and website, a company-domain email, campaign brief, deliverables, budget and currency, dates, payment schedule, usage rights, exclusivity terms, and draft contract. No campaign is confirmed until final owner approval."
            else:
                reply = "Thank you. The proposal has passed initial automated checks and has been forwarded for final owner review. No campaign is accepted until scope, payment, disclosures, usage rights, and contract terms are approved in writing."
            return ReplyPlan(reply_text=reply, category=decision.category, requires_owner=True, promotion=assessment)
        if decision.category == MessageCategory.GREETING:
            return ReplyPlan(reply_text=f"Hi! Thanks for messaging {self.settings.brand_name}. I’m the account’s AI-assisted inbox manager. How may I help?", category=decision.category)
        if decision.category == MessageCategory.CRYPTO_QUESTION:
            return ReplyPlan(reply_text="I can explain our latest market signals and risks, but I cannot guarantee price movements or provide personal financial advice. Tell me the coin or post you are asking about.", category=decision.category)
        if decision.category == MessageCategory.COMPLAINT:
            return ReplyPlan(reply_text="Thank you for raising this. I’m recording the issue for review. Please share the post date or screenshot and the specific information you believe is incorrect.", category=decision.category, requires_owner=True)
        return ReplyPlan(reply_text="Thanks for your message. Please share a little more detail so I can help accurately.", category=decision.category)
