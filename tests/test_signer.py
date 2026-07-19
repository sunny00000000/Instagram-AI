import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cryptopulse.config import Settings
from cryptopulse.services.signer import MediaURLSigner


def test_signed_media_url_round_trip(tmp_path: Path):
    settings = Settings(
        dry_run=True,
        public_base_url="https://example.test",
        media_signing_secret="test-secret-that-is-long-enough",
        media_root=tmp_path,
    )
    signer = MediaURLSigner(settings)
    url = signer.sign_path("run/file.png", expires_at=int(time.time()) + 100)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert signer.verify("run/file.png", int(query["exp"][0]), query["sig"][0])
    assert not signer.verify("run/other.png", int(query["exp"][0]), query["sig"][0])
    assert not signer.verify("run/file.png", int(time.time()) - 1, query["sig"][0])
