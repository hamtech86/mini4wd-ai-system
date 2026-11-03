import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from measurement_310.session_tag_allocator import (
    JournalUntrusted, MAX_TAG, SessionTagAllocator, TagExhausted,
)

def test_allocations_are_monotonic_and_persisted(tmp_path):
    path = tmp_path / "tags.jsonl"
    allocator = SessionTagAllocator(path, "motor-A", initial_high_water=40)
    assert [allocator.allocate().tag, allocator.allocate().tag] == [41, 42]
    assert SessionTagAllocator(path, "motor-A").allocate().tag == 43

def test_namespace_mismatch_fails_closed(tmp_path):
    path = tmp_path / "tags.jsonl"
    SessionTagAllocator(path, "namespace-A").allocate()
    with pytest.raises(JournalUntrusted):
        SessionTagAllocator(path, "namespace-B").allocate()

def test_missing_journal_without_trusted_high_water_fails_closed(tmp_path):
    with pytest.raises(JournalUntrusted):
        SessionTagAllocator(tmp_path / "missing.jsonl", "fixed").allocate()

@pytest.mark.parametrize("damage", ["truncate", "corrupt", "duplicate"])
def test_damaged_journal_fails_closed(tmp_path, damage):
    path = tmp_path / "tags.jsonl"
    SessionTagAllocator(path, "fixed").allocate()
    data = path.read_bytes()
    if damage == "truncate": path.write_bytes(data[:-2])
    elif damage == "corrupt": path.write_bytes(data.replace(b'"tag":1', b'"tag":9'))
    else: path.write_bytes(data + data)
    with pytest.raises(JournalUntrusted):
        SessionTagAllocator(path, "fixed").allocate()

def test_old_backup_is_not_used_as_recovery_source(tmp_path):
    path = tmp_path / "tags.jsonl"
    allocator = SessionTagAllocator(path, "fixed")
    allocator.allocate()
    backup = tmp_path / "tags.old"
    backup.write_bytes(path.read_bytes())
    allocator.allocate()
    # Without an external monotonic anchor, restoring an old valid journal is
    # not detectable by a hash chain stored only inside that journal.
    path.write_bytes(backup.read_bytes())
    with pytest.raises(JournalUntrusted):
        SessionTagAllocator(path, "fixed").allocate()

def test_exhaustion_never_wraps(tmp_path, monkeypatch):
    import measurement_310.session_tag_allocator as allocator_module
    monkeypatch.setattr(allocator_module, "MAX_TAG", 2)
    allocator = SessionTagAllocator(tmp_path / "tags.jsonl", "fixed")
    assert allocator.allocate().tag == 1
    assert allocator.allocate().tag == 2
    with pytest.raises(TagExhausted):
        allocator.allocate()

def test_concurrent_allocations_are_unique(tmp_path):
    allocator = SessionTagAllocator(tmp_path / "tags.jsonl", "fixed")
    with ThreadPoolExecutor(max_workers=8) as pool:
        tags = list(pool.map(lambda _: allocator.allocate().tag, range(40)))
    assert sorted(tags) == list(range(1, 41))
    assert len(set(tags)) == 40

def test_allocation_returns_after_durable_append(tmp_path):
    path = tmp_path / "tags.jsonl"
    assert SessionTagAllocator(path, "fixed").allocate().tag == 1
    assert path.read_bytes().endswith(b"\n")
    assert json.loads(path.read_text().splitlines()[0])["body"]["tag"] == 1
