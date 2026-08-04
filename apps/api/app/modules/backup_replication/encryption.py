"""Bounded authenticated encryption for backup artifacts.

The implementation uses the declared `cryptography` package and keeps only
one bounded chunk in memory at a time. Each chunk is encrypted with a unique
nonce and authenticated metadata; the key never enters logs, database rows, or
API responses.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

CHUNK_SIZE = 1024 * 1024
NONCE_SIZE = 12
TAG_SIZE = 16
KEY_SIZE = 32
MAGIC = b"NEXUS-BKP-2\n"


class EncryptionError(ValueError):
    """Raised when a backup cannot be encrypted or verified safely."""


def _key_bytes(raw_key: str) -> bytes:
    """Decode a hexadecimal 256-bit key without accepting ambiguous input."""
    value = raw_key.strip()
    if len(value) != KEY_SIZE * 2:
        raise EncryptionError("backup_key_invalid")
    try:
        key = bytes.fromhex(value)
    except ValueError as exc:
        raise EncryptionError("backup_key_invalid") from exc
    if len(key) != KEY_SIZE:
        raise EncryptionError("backup_key_invalid")
    return key


def _cryptography_backend():
    """Load the optional audited cryptography backend lazily."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise EncryptionError("encryption_backend_unavailable") from exc
    return AESGCM


def _associated_data(index: int, plaintext_size: int, source_size: int, chunk_count: int) -> bytes:
    """Bind each chunk to its sequence and immutable file framing metadata."""
    return MAGIC + source_size.to_bytes(8, "big") + chunk_count.to_bytes(4, "big") + index.to_bytes(8, "big") + plaintext_size.to_bytes(4, "big")


def encrypt_file(source: Path, destination: Path, raw_key: str) -> tuple[int, str]:
    """Encrypt a file as independently authenticated bounded AES-GCM chunks."""
    key = _key_bytes(raw_key)
    AESGCM = _cryptography_backend()
    destination.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    cipher = AESGCM(key)
    total = 0
    digest = hashlib.sha256()
    try:
        source_size = source.stat().st_size
        expected_chunks = (source_size + CHUNK_SIZE - 1) // CHUNK_SIZE
        with source.open("rb") as input_stream, destination.open("wb") as output_stream:
            output_stream.write(MAGIC)
            output_stream.write(source_size.to_bytes(8, "big"))
            output_stream.write(expected_chunks.to_bytes(4, "big"))
            index = 0
            while True:
                plaintext = input_stream.read(CHUNK_SIZE)
                if not plaintext:
                    break
                nonce = os.urandom(NONCE_SIZE)
                aad = _associated_data(index, len(plaintext), source_size, expected_chunks)
                ciphertext = cipher.encrypt(nonce, plaintext, aad)
                output_stream.write(len(plaintext).to_bytes(4, "big"))
                output_stream.write(nonce)
                output_stream.write(ciphertext)
                digest.update(nonce)
                digest.update(ciphertext)
                total += len(plaintext)
                index += 1
            if total != source_size or index != expected_chunks:
                raise EncryptionError("backup_encryption_failed")
            output_stream.flush()
            os.fsync(output_stream.fileno())
    except (OSError, ValueError) as exc:
        destination.unlink(missing_ok=True)
        if isinstance(exc, EncryptionError):
            raise
        raise EncryptionError("backup_encryption_failed") from exc
    return total, digest.hexdigest()


def verify_file(path: Path, raw_key: str) -> tuple[int, str]:
    """Authenticate every encrypted chunk without writing decrypted data."""
    key = _key_bytes(raw_key)
    AESGCM = _cryptography_backend()
    cipher = AESGCM(key)
    total = 0
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            if stream.read(len(MAGIC)) != MAGIC:
                raise EncryptionError("encrypted_backup_invalid")
            header_size_bytes = stream.read(8)
            chunk_count_bytes = stream.read(4)
            if len(header_size_bytes) != 8 or len(chunk_count_bytes) != 4:
                raise EncryptionError("encrypted_backup_invalid")
            header_size = int.from_bytes(header_size_bytes, "big")
            expected_chunks = int.from_bytes(chunk_count_bytes, "big")
            if header_size < 0 or expected_chunks != ((header_size + CHUNK_SIZE - 1) // CHUNK_SIZE):
                raise EncryptionError("encrypted_backup_invalid")
            index = 0
            while True:
                size_bytes = stream.read(4)
                if not size_bytes:
                    break
                if len(size_bytes) != 4:
                    raise EncryptionError("encrypted_backup_invalid")
                size = int.from_bytes(size_bytes, "big")
                if not 0 < size <= CHUNK_SIZE:
                    raise EncryptionError("encrypted_backup_invalid")
                nonce = stream.read(NONCE_SIZE)
                ciphertext = stream.read(size + TAG_SIZE)
                if len(nonce) != NONCE_SIZE or len(ciphertext) != size + TAG_SIZE:
                    raise EncryptionError("encrypted_backup_invalid")
                try:
                    plaintext = cipher.decrypt(nonce, ciphertext, _associated_data(index, size, header_size, expected_chunks))
                except Exception as exc:
                    raise EncryptionError("encrypted_backup_invalid") from exc
                if len(plaintext) != size:
                    raise EncryptionError("encrypted_backup_invalid")
                digest.update(nonce)
                digest.update(ciphertext)
                total += size
                index += 1
            if index != expected_chunks or total != header_size:
                raise EncryptionError("encrypted_backup_invalid")
    except EncryptionError:
        raise
    except (OSError, ValueError) as exc:
        raise EncryptionError("encrypted_backup_invalid") from exc
    return total, digest.hexdigest()
