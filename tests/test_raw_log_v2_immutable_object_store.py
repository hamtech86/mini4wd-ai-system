from __future__ import annotations

import hashlib
import os
import threading

import pytest

import raw_log_v2.immutable_object_store as object_store
from raw_log_v2.immutable_object_store import (
    ImmutableObjectStore,
    ObjectIntegrityError,
    PublicationError,
)


def test_put_bytes_preserves_exact_binary_payload_and_hash(tmp_path):
    payload = b"DATA,1\r\n\xff\x00\x80\n"
    store = ImmutableObjectStore(tmp_path)

    receipt = store.put_bytes(payload)

    assert receipt.content_hash == hashlib.sha256(payload).hexdigest()
    assert receipt.byte_length == len(payload)
    assert receipt.created is True
    assert receipt.path.read_bytes() == payload
    assert store.get_bytes(receipt.content_hash) == payload


def test_empty_payload_is_stored_as_exact_empty_bytes(tmp_path):
    store = ImmutableObjectStore(tmp_path)

    receipt = store.put_bytes(b"")

    assert receipt.byte_length == 0
    assert receipt.content_hash == hashlib.sha256(b"").hexdigest()
    assert store.get_bytes(receipt.content_hash) == b""


def test_identical_payload_is_idempotent_noop_without_overwrite(tmp_path):
    store = ImmutableObjectStore(tmp_path)
    payload = b"one\r\ntwo\n"

    first = store.put_bytes(payload)
    second = store.put_bytes(payload)

    assert first.created is True
    assert second.created is False
    assert first.path == second.path
    assert first.path.read_bytes() == payload
    assert list(tmp_path.glob(".rawlog-v2-staging-*")) == []


def test_non_bytes_payload_is_rejected(tmp_path):
    store = ImmutableObjectStore(tmp_path)

    with pytest.raises(TypeError):
        store.put_bytes(bytearray(b"mutable"))

    with pytest.raises(TypeError):
        store.put_bytes("decoded text")


def test_root_must_be_existing_absolute_real_directory(tmp_path):
    missing = tmp_path / "missing"

    with pytest.raises(ValueError):
        ImmutableObjectStore(missing)

    with pytest.raises(ValueError):
        ImmutableObjectStore("relative/path")

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError):
        ImmutableObjectStore(link)


def test_corrupt_existing_object_fails_closed(tmp_path):
    store = ImmutableObjectStore(tmp_path)
    payload = b"immutable source"
    receipt = store.put_bytes(payload)
    receipt.path.write_bytes(b"tampered")

    with pytest.raises(ObjectIntegrityError):
        store.get_bytes(receipt.content_hash)

    with pytest.raises(ObjectIntegrityError):
        store.put_bytes(payload)


def test_file_fsync_failure_does_not_publish_object(tmp_path, monkeypatch):
    store = ImmutableObjectStore(tmp_path)
    payload = b"must not publish"
    real_fsync = os.fsync

    def fail_fsync(_fd):
        raise OSError("injected file fsync failure")

    monkeypatch.setattr(object_store.os, "fsync", fail_fsync)

    with pytest.raises(PublicationError):
        store.put_bytes(payload)

    expected = hashlib.sha256(payload).hexdigest()
    assert not (tmp_path / expected).exists()
    assert list(tmp_path.glob(".rawlog-v2-staging-*")) == []
    monkeypatch.setattr(object_store.os, "fsync", real_fsync)


def test_directory_fsync_failure_leaves_uncertain_object_for_inspection(
    tmp_path, monkeypatch
):
    store = ImmutableObjectStore(tmp_path)
    payload = b"published but durability uncertain"
    real_fsync = os.fsync
    calls = {"count": 0}

    def fail_second_fsync(fd):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("injected directory fsync failure")
        return real_fsync(fd)

    monkeypatch.setattr(object_store.os, "fsync", fail_second_fsync)

    with pytest.raises(PublicationError):
        store.put_bytes(payload)

    expected = hashlib.sha256(payload).hexdigest()
    assert (tmp_path / expected).read_bytes() == payload

    # Once the directory fsync succeeds, retry verifies the existing bytes
    # and returns a no-op receipt; it does not rewrite the object.
    monkeypatch.setattr(object_store.os, "fsync", real_fsync)
    receipt = store.put_bytes(payload)
    assert receipt.created is False
    assert receipt.path.read_bytes() == payload


def test_concurrent_identical_publication_has_one_immutable_object(tmp_path):
    store = ImmutableObjectStore(tmp_path)
    payload = b"same bytes from two writers"
    receipts = []
    errors = []

    def publish():
        try:
            receipts.append(store.put_bytes(payload))
        except Exception as exc:  # pragma: no cover - diagnostic collection
            errors.append(exc)

    writers = [threading.Thread(target=publish) for _ in range(2)]
    for writer in writers:
        writer.start()
    for writer in writers:
        writer.join()

    assert errors == []
    assert len(receipts) == 2
    assert sorted(receipt.created for receipt in receipts) == [False, True]
    assert len(list(tmp_path.glob("[0-9a-f]" * 64))) == 1
    assert receipts[0].path.read_bytes() == payload


def test_hash_locator_must_be_canonical_sha256(tmp_path):
    store = ImmutableObjectStore(tmp_path)

    for invalid in ("", "A" * 64, "g" * 64, "0" * 63, None):
        with pytest.raises(ValueError):
            store.get_bytes(invalid)



def test_large_payload_is_preserved_without_text_transformation(tmp_path):
    store = ImmutableObjectStore(tmp_path)
    payload = (bytes(range(256)) + b"\\r\\n") * 4096

    receipt = store.put_bytes(payload)

    assert receipt.byte_length == len(payload)
    assert receipt.content_hash == hashlib.sha256(payload).hexdigest()
    assert store.get_bytes(receipt.content_hash) == payload


def test_short_writes_are_completed_until_all_bytes_are_stored(tmp_path, monkeypatch):
    store = ImmutableObjectStore(tmp_path)
    payload = b"short-write-boundary" * 100
    real_write = os.write
    write_sizes = []

    def short_write(fd, data):
        chunk = data[:7]
        write_sizes.append(len(chunk))
        return real_write(fd, chunk)

    monkeypatch.setattr(object_store.os, "write", short_write)
    receipt = store.put_bytes(payload)

    assert len(write_sizes) > 1
    assert store.get_bytes(receipt.content_hash) == payload


def test_partial_write_failure_does_not_publish_final_object(tmp_path, monkeypatch):
    store = ImmutableObjectStore(tmp_path)
    payload = b"partial-write-must-not-publish" * 10
    real_write = os.write
    calls = {"count": 0}

    def fail_after_partial(fd, data):
        calls["count"] += 1
        if calls["count"] == 1:
            return real_write(fd, data[:5])
        raise OSError("injected partial write failure")

    monkeypatch.setattr(object_store.os, "write", fail_after_partial)

    with pytest.raises(PublicationError):
        store.put_bytes(payload)

    expected = hashlib.sha256(payload).hexdigest()
    assert not (tmp_path / expected).exists()
    assert list(tmp_path.glob(".rawlog-v2-staging-*")) == []
