from __future__ import annotations

import re
from urllib.parse import urlparse

from cryptopulse.schemas_messaging import PromotionAssessment

SUSPICIOUS = (
    "seed phrase", "private key", "otp", "verification fee", "processing fee",
    "gift card", "guaranteed profit", "100x", "buy first", "urgent payment",
)


def assess_promotion(text: str) -> PromotionAssessment:
    lower = text.lower()
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    urls = re.findall(r"https?://[^\s]+", text)
    budget_match = re.search(r"(?:\$|€|£|₹)\s?[\d,.]+|\b\d+[\d,.]*\s?(?:usd|eur|gbp|inr)\b", text, re.I)
    red_flags = [term for term in SUSPICIOUS if term in lower]
    website = urls[0].rstrip(".,)") if urls else None
    email = emails[0] if emails else None
    domain_match = False
    if website and email:
        web_domain = urlparse(website).hostname or ""
        email_domain = email.split("@", 1)[1]
        domain_match = web_domain.removeprefix("www.").endswith(email_domain)
    identity = 20 + (25 if website else 0) + (25 if email else 0) + (20 if domain_match else 0)
    identity = max(0, min(100, identity - len(red_flags) * 20))
    safety = max(0, min(100, 85 - len(red_flags) * 30))
    scam = min(100, len(red_flags) * 30 + (20 if not website else 0) + (15 if not email else 0))
    missing = []
    for label, present in (
        ("official company website", bool(website)),
        ("company-domain email", bool(email)),
        ("campaign deliverables", any(k in lower for k in ("reel", "story", "post", "carousel", "deliverable"))),
        ("budget", bool(budget_match)),
        ("contract and usage rights", any(k in lower for k in ("contract", "usage rights", "license"))),
        ("campaign dates", any(k in lower for k in ("deadline", "date", "campaign period"))),
    ):
        if not present:
            missing.append(label)
    if red_flags or scam >= 70:
        recommendation = "reject"
    elif missing:
        recommendation = "request_information"
    else:
        recommendation = "owner_review"
    brand = None
    brand_match = re.search(r"(?:from|representing|brand)\s+([A-Z][\w& .-]{2,40})", text)
    if brand_match:
        brand = brand_match.group(1).strip(" .")
    return PromotionAssessment(
        brand_name=brand,
        official_website=website,
        contact_email=email,
        budget=budget_match.group(0) if budget_match else None,
        deliverables=text[:300],
        identity_score=identity,
        brand_safety_score=safety,
        scam_probability=scam,
        missing_fields=missing,
        red_flags=red_flags,
        recommendation=recommendation,
    )
