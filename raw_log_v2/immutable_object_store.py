"""Immutable, byte-exact content-addressed storage for opaque RawLog payloads.

This module deliberately does not define a Capture boundary, package cardinality,
DB identity, UUID issuer, Measurement association, or retry key. The SHA-256
digest is only a storage locator and integrity check; it is not a DB identity.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Union


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class ObjectStoreError(RuntimeError):
    """Base class for fail-closed object-store errors."""


class ObjectConflictError(ObjectStoreError):
    """An immutable destination already exists with different bytes."""


class ObjectIntegrityError(ObjectStoreError):
    """Stored bytes do not match their content-addressed SHA-256."""


class PublicationError(ObjectStoreError):
    """Atomic publication or durability could not be established."""


@dataclass(frozen=True)
class StoredObject:
    """Receipt for an opaque byte object; content_hash is not a DB identity."""

    content_hash: str
    byte_length: int
    path: Path
    created: bool


class ImmutableObjectStore:
    """Publish exact byte buffers into an existing directory without overwrite.

    The caller owns the meaning and boundary of the payload. This class stores
    exactly that buffer and never decodes, parses, normalizes, or frames it.
    The root directory must already exist; it is never created implicitly.
    """

    def __init__(self, root: Union[str, os.PathLike[str]]) -> None:
        root_path = Path(root)
        if not root_path.is_absolute():
            raise ValueError("object-store root must be an absolute path")
        try:
            root_stat = root_path.lstat()
        except FileNotFoundError as exc:
            raise ValueError("object-store root must already exist") from exc
        if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
            raise ValueError("object-store root must be a real directory, not a symlink")
        self._root = root_path

    @property
    def root(self) -> Path:
        return self._root

    @staticmethod
    def digest(payload: bytes) -> str:
        if not isinstance(payload, bytes):
            raise TypeError("payload must be immutable bytes")
        return hashlib.sha256(payload).hexdigest()

    def put_bytes(self, payload: bytes) -> StoredObject:
        """Atomically publish payload; identical existing bytes are a no-op."""
        if not isinstance(payload, bytes):
            raise TypeError("payload must be immutable bytes")

        content_hash = self.digest(payload)
        destination = self._root / content_hash

        if destination.exists() or destination.is_symlink():
            existing = self._read_verified(content_hash)
            if existing != payload:
                raise ObjectConflictError(
                    "content-addressed destination exists with different bytes"
                )
            self._fsync_directory()
            return StoredObject(content_hash, len(payload), destination, False)

        fd, temporary_name = tempfile.mkstemp(
            prefix=".rawlog-v2-staging-", dir=str(self._root)
        )
        temporary = Path(temporary_name)
        published = False
        try:
            try:
                view = memoryview(payload)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        raise PublicationError("staging write made no progress")
                    view = view[written:]
                os.fsync(fd)
            finally:
                os.close(fd)

            staged = self._read_regular_file(temporary)
            if staged != payload or hashlib.sha256(staged).hexdigest() != content_hash:
                raise ObjectIntegrityError("staging read-back differs from input bytes")

            try:
                # Hard-link publication is atomic and never replaces a destination.
                os.link(str(temporary), str(destination))
                published = True
            except FileExistsError:
                existing = self._read_verified(content_hash)
                if existing != payload:
                    raise ObjectConflictError(
                        "concurrent publisher created a conflicting destination"
                    )

            # A failed directory fsync leaves the final name in place but its
            # durability is uncertain. Do not delete or overwrite that evidence.
            self._fsync_directory()
            final_bytes = self._read_verified(content_hash)
            if final_bytes != payload:
                raise ObjectIntegrityError("published read-back differs from input bytes")

            return StoredObject(content_hash, len(payload), destination, published)
        except ObjectStoreError:
            raise
        except OSError as exc:
            raise PublicationError(f"object publication failed: {exc}") from exc
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                # A staging remnant is not a committed object. Leave it for
                # explicit inspection rather than risking deletion of evidence.
                pass

    def get_bytes(self, content_hash: str) -> bytes:
        """Read and verify an object by its SHA-256 storage locator."""
        self._validate_hash(content_hash)
        return self._read_verified(content_hash)

    def _read_verified(self, content_hash: str) -> bytes:
        path = self._root / content_hash
        payload = self._read_regular_file(path)
        actual = hashlib.sha256(payload).hexdigest()
        if actual != content_hash:
            raise ObjectIntegrityError(
                f"stored object hash mismatch: expected {content_hash}, got {actual}"
            )
        return payload

    @staticmethod
    def _validate_hash(content_hash: str) -> None:
        if not isinstance(content_hash, str) or not _HASH_RE.fullmatch(content_hash):
            raise ValueError("content_hash must be 64 lowercase hexadecimal characters")

    @staticmethod
    def _read_regular_file(path: Path) -> bytes:
        try:
            before = path.lstat()
        except FileNotFoundError:
            raise
        if not stat.S_ISREG(before.st_mode):
            raise ObjectIntegrityError("object path is not a regular file")

        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(str(path), flags)
        try:
            after = os.fstat(fd)
            if not stat.S_ISREG(after.st_mode):
                raise ObjectIntegrityError("opened object is not a regular file")
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                raise ObjectIntegrityError("object path changed during open")
            chunks = []
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(fd)

    def _fsync_directory(self) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        try:
            fd = os.open(str(self._root), flags)
        except OSError as exc:
            raise PublicationError(f"directory open for fsync failed: {exc}") from exc
        try:
            os.fsync(fd)
        except OSError as exc:
            raise PublicationError(f"directory fsync failed: {exc}") from exc
        finally:
            os.close(fd)
