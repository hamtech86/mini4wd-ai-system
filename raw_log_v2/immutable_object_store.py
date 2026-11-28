"""Immutable, byte-exact content-addressed storage for opaque RawLog payloads.

This module deliberately does not define a Capture boundary, package cardinality,
DB identity, UUID issuer, Measurement association, or retry key. The SHA-256
digest is only a storage locator and integrity check; it is not a DB identity.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Union


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class ObjectStoreError(RuntimeError):
    """Base class for fail-closed object-store errors."""


class ObjectConflictError(ObjectStoreError):
    """An immutable destination already exists with different bytes."""


class ObjectIntegrityError(ObjectStoreError):
    """Stored bytes do not match their content-addressed SHA-256."""


class PublicationError(ObjectStoreError):
    """Atomic publication or durability could not be established."""


class RootIdentityError(ObjectStoreError):
    """The configured root path no longer identifies its original directory."""


@dataclass(frozen=True)
class StoredObject:
    """Receipt for an opaque byte object; content_hash is not a DB identity."""

    content_hash: str
    byte_length: int
    path: Path
    created: bool


class ImmutableObjectStore:
    """Publish exact byte buffers into an existing, identity-pinned directory.

    The caller owns the meaning and boundary of the payload. This class stores
    exactly that buffer and never decodes, parses, normalizes, or frames it.
    The root directory must already exist; it is never created implicitly.

    Every operation opens the configured root and verifies its device/inode
    identity against construction-time identity. File operations then use that
    verified directory descriptor, so a later path replacement cannot redirect
    reads or writes into a different directory.
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

        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(str(root_path), flags)
        except OSError as exc:
            raise ValueError(f"object-store root cannot be opened safely: {exc}") from exc
        try:
            opened = os.fstat(fd)
            if not stat.S_ISDIR(opened.st_mode):
                raise ValueError("object-store root must be a real directory")
            if (root_stat.st_dev, root_stat.st_ino) != (opened.st_dev, opened.st_ino):
                raise ValueError("object-store root changed during initialization")
            self._root_identity = (opened.st_dev, opened.st_ino)
        finally:
            os.close(fd)
        self._root = root_path

    @property
    def root(self) -> Path:
        return self._root

    @staticmethod
    def digest(payload: bytes) -> str:
        if not isinstance(payload, bytes):
            raise TypeError("payload must be immutable bytes")
        return hashlib.sha256(payload).hexdigest()

    @contextmanager
    def _verified_root_fd(self) -> Iterator[int]:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(str(self._root), flags)
        except OSError as exc:
            raise RootIdentityError(f"configured object-store root is unavailable: {exc}") from exc
        try:
            current = os.fstat(fd)
            if not stat.S_ISDIR(current.st_mode):
                raise RootIdentityError("configured object-store root is not a directory")
            if (current.st_dev, current.st_ino) != self._root_identity:
                raise RootIdentityError("configured object-store root identity changed")
            yield fd
        finally:
            os.close(fd)

    def put_bytes(self, payload: bytes) -> StoredObject:
        """Atomically publish payload; identical existing bytes are a no-op."""
        if not isinstance(payload, bytes):
            raise TypeError("payload must be immutable bytes")

        content_hash = self.digest(payload)
        destination = content_hash
        with self._verified_root_fd() as root_fd:
            try:
                self._read_verified_at(root_fd, destination)
            except FileNotFoundError:
                pass
            else:
                existing = self._read_verified_at(root_fd, destination)
                if existing != payload:
                    raise ObjectConflictError(
                        "content-addressed destination exists with different bytes"
                    )
                os.fsync(root_fd)
                return StoredObject(content_hash, len(payload), self._root / destination, False)

            temporary_name = f".rawlog-v2-staging-{secrets.token_hex(16)}"
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(temporary_name, flags, 0o600, dir_fd=root_fd)
            except OSError as exc:
                raise PublicationError(f"staging file creation failed: {exc}") from exc

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

                staged = self._read_regular_file_at(root_fd, temporary_name)
                if staged != payload or hashlib.sha256(staged).hexdigest() != content_hash:
                    raise ObjectIntegrityError("staging read-back differs from input bytes")

                try:
                    os.link(
                        temporary_name,
                        destination,
                        src_dir_fd=root_fd,
                        dst_dir_fd=root_fd,
                        follow_symlinks=False,
                    )
                    published = True
                except FileExistsError:
                    existing = self._read_verified_at(root_fd, destination)
                    if existing != payload:
                        raise ObjectConflictError(
                            "concurrent publisher created a conflicting destination"
                        )
                    published = False

                # If this fails, preserve the published name as evidence; durability
                # is uncertain and the caller must not assume successful publication.
                os.fsync(root_fd)
                final_bytes = self._read_verified_at(root_fd, destination)
                if final_bytes != payload:
                    raise ObjectIntegrityError("published read-back differs from input bytes")
                return StoredObject(content_hash, len(payload), self._root / destination, published)
            except ObjectStoreError:
                raise
            except OSError as exc:
                raise PublicationError(f"object publication failed: {exc}") from exc
            finally:
                try:
                    os.unlink(temporary_name, dir_fd=root_fd)
                except FileNotFoundError:
                    pass
                except OSError:
                    # A staging remnant is not a committed object. Leave it for
                    # explicit inspection rather than risking deletion of evidence.
                    pass

    def get_bytes(self, content_hash: str) -> bytes:
        """Read and verify an object by its SHA-256 storage locator."""
        self._validate_hash(content_hash)
        with self._verified_root_fd() as root_fd:
            return self._read_verified_at(root_fd, content_hash)

    def _read_verified_at(self, root_fd: int, content_hash: str) -> bytes:
        payload = self._read_regular_file_at(root_fd, content_hash)
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
    def _read_regular_file_at(root_fd: int, name: str) -> bytes:
        try:
            before = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            raise
        if not stat.S_ISREG(before.st_mode):
            raise ObjectIntegrityError("object path is not a regular file")

        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(name, flags, dir_fd=root_fd)
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
