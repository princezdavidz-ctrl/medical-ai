"""Signature and freshness verification for offline medical-knowledge packages.

This module verifies package integrity before any future importer may stage content.
It does not publish clinical knowledge or bypass the governed review workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import json
import re
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_SCHEMA_VERSIONS = frozenset({"1"})


class OfflinePackageRejected(ValueError):
    """Raised when an offline package cannot be trusted or is no longer current."""


@dataclass(frozen=True, slots=True)
class OfflineKnowledgeManifest:
    package_id: str
    schema_version: str
    snapshot_version: str
    jurisdiction: str
    issued_at: datetime
    expires_at: datetime
    document_count: int
    payload_sha256: str
    signing_key_id: str

    def canonical_bytes(self) -> bytes:
        """Return the exact canonical bytes covered by the publisher signature."""
        payload = {
            "document_count": self.document_count,
            "expires_at": self.expires_at.astimezone(timezone.utc).isoformat(),
            "issued_at": self.issued_at.astimezone(timezone.utc).isoformat(),
            "jurisdiction": self.jurisdiction,
            "package_id": self.package_id,
            "payload_sha256": self.payload_sha256,
            "schema_version": self.schema_version,
            "signing_key_id": self.signing_key_id,
            "snapshot_version": self.snapshot_version,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, slots=True)
class VerifiedOfflinePackage:
    package_id: str
    snapshot_version: str
    jurisdiction: str
    payload_sha256: str
    document_count: int
    signing_key_id: str
    expires_at: datetime


def verify_offline_package(
    *,
    manifest: OfflineKnowledgeManifest,
    payload: bytes,
    signature_b64: str,
    trusted_public_keys: Mapping[str, bytes],
    allowed_jurisdictions: frozenset[str],
    now: datetime | None = None,
    maximum_age: timedelta = timedelta(days=30),
) -> VerifiedOfflinePackage:
    """Verify publisher signature, payload digest, jurisdiction and package freshness."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or manifest.issued_at.tzinfo is None or manifest.expires_at.tzinfo is None:
        raise OfflinePackageRejected("timezone_required")
    if not manifest.package_id.strip() or not manifest.snapshot_version.strip():
        raise OfflinePackageRejected("package_identity_missing")
    if manifest.schema_version not in _SUPPORTED_SCHEMA_VERSIONS:
        raise OfflinePackageRejected("unsupported_package_schema")
    if manifest.document_count < 1:
        raise OfflinePackageRejected("empty_knowledge_package")
    if not _SHA256.fullmatch(manifest.payload_sha256):
        raise OfflinePackageRejected("invalid_payload_digest")
    if manifest.jurisdiction not in allowed_jurisdictions:
        raise OfflinePackageRejected("jurisdiction_not_allowed")
    if manifest.issued_at > current:
        raise OfflinePackageRejected("package_issued_in_future")
    if manifest.expires_at <= current:
        raise OfflinePackageRejected("package_expired")
    if manifest.expires_at <= manifest.issued_at:
        raise OfflinePackageRejected("invalid_package_validity_window")
    if current - manifest.issued_at > maximum_age:
        raise OfflinePackageRejected("package_exceeds_maximum_age")

    actual_digest = hashlib.sha256(payload).hexdigest()
    if actual_digest != manifest.payload_sha256:
        raise OfflinePackageRejected("payload_digest_mismatch")

    public_key_bytes = trusted_public_keys.get(manifest.signing_key_id)
    if public_key_bytes is None:
        raise OfflinePackageRejected("untrusted_signing_key")
    if len(public_key_bytes) != 32:
        raise OfflinePackageRejected("invalid_trusted_public_key")

    try:
        signature = base64.b64decode(signature_b64, validate=True)
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
            signature, manifest.canonical_bytes()
        )
    except (ValueError, InvalidSignature):
        raise OfflinePackageRejected("package_signature_invalid") from None

    return VerifiedOfflinePackage(
        package_id=manifest.package_id,
        snapshot_version=manifest.snapshot_version,
        jurisdiction=manifest.jurisdiction,
        payload_sha256=actual_digest,
        document_count=manifest.document_count,
        signing_key_id=manifest.signing_key_id,
        expires_at=manifest.expires_at,
    )


@dataclass(frozen=True, slots=True)
class OfflineSyncCursor:
    sequence: int = 0
    last_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class OfflineSyncEvent:
    event_id: str
    sequence: int
    payload_sha256: str


def classify_sync_event(
    *, cursor: OfflineSyncCursor, event: OfflineSyncEvent
) -> str:
    """Classify a queued sync event without applying it or silently skipping gaps."""
    if not event.event_id.strip() or event.sequence < 1:
        return "invalid"
    if not _SHA256.fullmatch(event.payload_sha256):
        return "invalid"
    if event.event_id == cursor.last_event_id or event.sequence <= cursor.sequence:
        return "duplicate_or_stale"
    if event.sequence != cursor.sequence + 1:
        return "sequence_gap"
    return "ready"
