from core.storage import (
    StoragePaths,
    append_audit,
    list_case_versions,
    list_cases,
    read_draft,
    write_case_meta,
    write_decision,
    write_draft,
    write_snapshot,
)


def _paths(tmp_path) -> StoragePaths:
    return StoragePaths(tmp_path)


def test_draft_round_trip(tmp_path):
    paths = _paths(tmp_path)
    write_draft(paths, "case1", 1, {"case_id": "case1", "version": 1})
    assert read_draft(paths, "case1")["case_id"] == "case1"


def test_latest_version_is_returned_by_default(tmp_path):
    paths = _paths(tmp_path)
    for version in (1, 2, 10):
        write_draft(paths, "case1", version, {"case_id": "case1", "version": version})

    assert list_case_versions(paths, "case1") == [1, 2, 10]
    assert read_draft(paths, "case1")["version"] == 10


def test_snapshot_and_decision_are_stored_per_version(tmp_path):
    paths = _paths(tmp_path)
    write_snapshot(paths, "case1", 1, {"overall_risk_score": 0.5})
    write_decision(paths, "case1", 1, {"decision_type": "REDUCE"})

    assert paths.snapshot_path("case1", 1).exists()
    assert paths.decision_path("case1", 1).exists()


def test_audit_log_appends(tmp_path):
    paths = _paths(tmp_path)
    append_audit(paths, "case1", {"action": "new_case"})
    append_audit(paths, "case1", {"action": "evaluate"})

    lines = paths.case_audit_path("case1").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_case_listing_includes_meta(tmp_path):
    paths = _paths(tmp_path)
    write_case_meta(paths, "case1", {"case_name": "Supplier failure"})
    assert list_cases(paths)[0]["case_name"] == "Supplier failure"
