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
    SessionTagAllocator(path, "namespace-A", initial_high_water=0).allocate()
    with pytest.raises(JournalUntrusted):
        SessionTagAllocator(path, "namespace-B").allocate()

def test_missing_journal_without_trusted_high_water_fails_closed(tmp_path):
    with pytest.raises(JournalUntrusted):
        SessionTagAllocator(tmp_path / "missing.jsonl", "fixed").allocate()

@pytest.mark.parametrize("damage", ["truncate", "corrupt", "duplicate"])
def test_damaged_journal_fails_closed(tmp_path, damage):
    path = tmp_path / "tags.jsonl"
    SessionTagAllocator(path, "fixed", initial_high_water=0).allocate()
    data = path.read_bytes()
    if damage == "truncate": path.write_bytes(data[:-2])
    elif damage == "corrupt": path.write_bytes(data.replace(b'"tag":1', b'"tag":9'))
    else: path.write_bytes(data + data)
    with pytest.raises(JournalUntrusted):
        SessionTagAllocator(path, "fixed", initial_high_water=0).allocate()

def test_old_backup_is_not_used_as_recovery_source(tmp_path):
    path = tmp_path / "tags.jsonl"
    allocator = SessionTagAllocator(path, "fixed", initial_high_water=0)
    allocator.allocate()
    backup = tmp_path / "tags.old"
    backup.write_bytes(path.read_bytes())
    allocator.allocate()
    # This exercises partial rollback only: the journal is restored while
    # the newer sibling anchor remains in place. Both files share a rollback
    # domain, so this test does not establish paired-backup rollback safety.
    path.write_bytes(backup.read_bytes())
    with pytest.raises(JournalUntrusted):
        SessionTagAllocator(path, "fixed", initial_high_water=0).allocate()

@pytest.mark.xfail(strict=True, reason="T01 blocker: journal and sibling anchor have no independent monotonic witness")
def test_paired_backup_rollback_does_not_reissue_a_previously_allocated_tag(tmp_path):
    path = tmp_path / "tags.jsonl"
    allocator = SessionTagAllocator(path, "fixed", initial_high_water=0)
    assert allocator.allocate().tag == 1

    # Preserve a mutually consistent older snapshot of both local files.
    old_journal = path.read_bytes()
    anchor_path = path.with_name(path.name + ".anchor")
    old_anchor = anchor_path.read_bytes()

    assert allocator.allocate().tag == 2

    # Roll back the entire local persistence pair, not just one member.
    path.write_bytes(old_journal)
    anchor_path.write_bytes(old_anchor)

    recovered = SessionTagAllocator(path, "fixed").allocate()
    # Correct behavior must fail closed or continue above 2. Current code
    # returns 2, demonstrating reuse after authentic paired rollback.
    assert recovered.tag > 2

def test_exhaustion_never_wraps(tmp_path, monkeypatch):
    import measurement_310.session_tag_allocator as allocator_module
    monkeypatch.setattr(allocator_module, "MAX_TAG", 2)
    allocator = SessionTagAllocator(tmp_path / "tags.jsonl", "fixed", initial_high_water=0)
    assert allocator.allocate().tag == 1
    assert allocator.allocate().tag == 2
    with pytest.raises(TagExhausted):
        allocator.allocate()

def test_concurrent_allocations_are_unique(tmp_path):
    allocator = SessionTagAllocator(tmp_path / "tags.jsonl", "fixed", initial_high_water=0)
    with ThreadPoolExecutor(max_workers=8) as pool:
        tags = list(pool.map(lambda _: allocator.allocate().tag, range(40)))
    assert sorted(tags) == list(range(1, 41))
    assert len(set(tags)) == 40

def test_allocation_returns_after_durable_append(tmp_path):
    path = tmp_path / "tags.jsonl"
    assert SessionTagAllocator(path, "fixed", initial_high_water=0).allocate().tag == 1
    assert path.read_bytes().endswith(b"\n")
    assert json.loads(path.read_text().splitlines()[0])["body"]["tag"] == 1


@pytest.mark.parametrize("fault", [
    "after_journal_write",
    "after_journal_fsync",
    "after_anchor_file_fsync",
    "after_anchor_replace",
    "before_anchor_dir_fsync",
])
def test_crash_boundary_never_reuses_an_uncertain_tag(tmp_path, fault):
    path = tmp_path / "tags.jsonl"
    allocator = SessionTagAllocator(path, "fixed", initial_high_water=0)
    with pytest.raises(Exception):
        allocator.allocate(fault_at=fault)

    # Recovery may either fail closed when journal/anchor disagree, or
    # continue after a fully replaced anchor. It must never return tag 1 again.
    try:
        recovered = SessionTagAllocator(path, "fixed", initial_high_water=0).allocate()
    except JournalUntrusted:
        return
    assert recovered.tag >= 2


def test_anchor_corruption_fails_closed(tmp_path):
    path = tmp_path / "tags.jsonl"
    allocator = SessionTagAllocator(path, "fixed", initial_high_water=0)
    allocator.allocate()
    anchor = path.with_name(path.name + ".anchor")
    anchor.write_bytes(b'{"damaged":true}\\n')
    with pytest.raises(JournalUntrusted):
        SessionTagAllocator(path, "fixed", initial_high_water=0).allocate()


def test_missing_anchor_fails_closed(tmp_path):
    path = tmp_path / "tags.jsonl"
    allocator = SessionTagAllocator(path, "fixed", initial_high_water=0)
    allocator.allocate()
    path.with_name(path.name + ".anchor").unlink()
    with pytest.raises(JournalUntrusted):
        SessionTagAllocator(path, "fixed", initial_high_water=0).allocate()
