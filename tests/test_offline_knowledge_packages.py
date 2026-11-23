from datetime import datetime, timedelta, timezone
import base64
import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.ai.offline_packages import (
    OfflineKnowledgeManifest,
    OfflinePackageRejected,
    OfflineSyncCursor,
    OfflineSyncEvent,
    classify_sync_event,
    verify_offline_package,
)

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
PAYLOAD = b'approved knowledge snapshot metadata and chunks'
PRIVATE_KEY = Ed25519PrivateKey.generate()
PUBLIC_KEY = PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)


def signed_package(*, payload: bytes = PAYLOAD, jurisdiction: str = "KE"):
    manifest = OfflineKnowledgeManifest(
        package_id="package-001",
        schema_version="1",
        snapshot_version="2026.11",
        jurisdiction=jurisdiction,
        issued_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(days=14),
        document_count=2,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        signing_key_id="publisher-key-1",
    )
    signature = base64.b64encode(PRIVATE_KEY.sign(manifest.canonical_bytes())).decode()
    return manifest, signature


def verify(manifest, signature, payload=PAYLOAD):
    return verify_offline_package(
        manifest=manifest,
        payload=payload,
        signature_b64=signature,
        trusted_public_keys={"publisher-key-1": PUBLIC_KEY},
        allowed_jurisdictions=frozenset({"KE", "INT"}),
        now=NOW,
    )


def test_signed_package_is_accepted():
    manifest, signature = signed_package()
    result = verify(manifest, signature)
    assert result.package_id == "package-001"
    assert result.snapshot_version == "2026.11"


def test_payload_tampering_is_rejected():
    manifest, signature = signed_package()
    with pytest.raises(OfflinePackageRejected, match="payload_digest_mismatch"):
        verify(manifest, signature, payload=b"tampered")


def test_unknown_signing_key_is_rejected():
    manifest, signature = signed_package()
    with pytest.raises(OfflinePackageRejected, match="untrusted_signing_key"):
        verify_offline_package(
            manifest=manifest,
            payload=PAYLOAD,
            signature_b64=signature,
            trusted_public_keys={},
            allowed_jurisdictions=frozenset({"KE"}),
            now=NOW,
        )


def test_expired_package_is_rejected():
    manifest, signature = signed_package()
    expired = OfflineKnowledgeManifest(
        package_id=manifest.package_id,
        schema_version=manifest.schema_version,
        snapshot_version=manifest.snapshot_version,
        jurisdiction=manifest.jurisdiction,
        issued_at=NOW - timedelta(days=40),
        expires_at=NOW - timedelta(days=1),
        document_count=manifest.document_count,
        payload_sha256=manifest.payload_sha256,
        signing_key_id=manifest.signing_key_id,
    )
    expired_signature = base64.b64encode(PRIVATE_KEY.sign(expired.canonical_bytes())).decode()
    with pytest.raises(OfflinePackageRejected, match="package_expired"):
        verify(expired, expired_signature)


def test_disallowed_jurisdiction_is_rejected():
    manifest, signature = signed_package(jurisdiction="UNKNOWN")
    with pytest.raises(OfflinePackageRejected, match="jurisdiction_not_allowed"):
        verify(manifest, signature)


def test_sync_cursor_accepts_only_next_sequence():
    cursor = OfflineSyncCursor(sequence=4, last_event_id="event-4")
    next_event = OfflineSyncEvent("event-5", 5, hashlib.sha256(b"x").hexdigest())
    assert classify_sync_event(cursor=cursor, event=next_event) == "ready"


def test_sync_duplicate_and_gap_are_not_applied():
    cursor = OfflineSyncCursor(sequence=4, last_event_id="event-4")
    duplicate = OfflineSyncEvent("event-4", 4, hashlib.sha256(b"x").hexdigest())
    gap = OfflineSyncEvent("event-6", 6, hashlib.sha256(b"x").hexdigest())
    assert classify_sync_event(cursor=cursor, event=duplicate) == "duplicate_or_stale"
    assert classify_sync_event(cursor=cursor, event=gap) == "sequence_gap"
