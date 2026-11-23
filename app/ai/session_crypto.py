"""Authenticated encryption for persisted AI conversation content."""
from __future__ import annotations

from collections.abc import Mapping
import base64
import json
import os
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SessionEncryptionError(RuntimeError):
    pass


class SessionCipher:
    """AES-256-GCM cipher with versioned keys and tenant/session-bound AAD."""

    def __init__(self, *, keys: Mapping[str, bytes], active_key_version: str) -> None:
        if active_key_version not in keys:
            raise SessionEncryptionError("active_session_key_version_missing")
        if any(len(key) != 32 for key in keys.values()):
            raise SessionEncryptionError("session_keys_must_be_256_bit")
        self._keys = dict(keys)
        self.active_key_version = active_key_version

    @classmethod
    def from_secret(cls, *, keyring_secret: str, active_key_version: str) -> "SessionCipher":
        try:
            encoded = json.loads(keyring_secret)
            keys = {
                version: base64.b64decode(value, validate=True)
                for version, value in encoded.items()
            }
        except (TypeError, ValueError, AttributeError):
            raise SessionEncryptionError("invalid_session_keyring") from None
        return cls(keys=keys, active_key_version=active_key_version)

    @staticmethod
    def associated_data(
        *,
        hospital_id: UUID,
        owner_user_id: UUID,
        session_id: UUID,
        sequence_number: int,
        role: str,
        key_version: str,
    ) -> bytes:
        return (
            f"{hospital_id}:{owner_user_id}:{session_id}:{sequence_number}:{role}:{key_version}"
        ).encode("utf-8")

    def encrypt(self, plaintext: str, *, associated_data: bytes) -> tuple[bytes, bytes, str]:
        if not isinstance(plaintext, str):
            raise SessionEncryptionError("session_content_must_be_text")
        nonce = os.urandom(12)
        key_version = self.active_key_version
        ciphertext = AESGCM(self._keys[key_version]).encrypt(
            nonce, plaintext.encode("utf-8"), associated_data
        )
        return ciphertext, nonce, key_version

    def decrypt(
        self,
        ciphertext: bytes,
        *,
        nonce: bytes,
        key_version: str,
        associated_data: bytes,
    ) -> str:
        key = self._keys.get(key_version)
        if key is None:
            raise SessionEncryptionError("session_decryption_key_version_unavailable")
        if len(nonce) != 12:
            raise SessionEncryptionError("invalid_session_nonce")
        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, associated_data)
            return plaintext.decode("utf-8")
        except (InvalidTag, UnicodeDecodeError):
            raise SessionEncryptionError("session_ciphertext_authentication_failed") from None
