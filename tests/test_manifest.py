from __future__ import annotations

import json
from pathlib import Path

import pytest

from img_dedupe.manifest import (
    ManifestError,
    apply_plan,
    build_apply_plan,
    load_manifest,
    validate_manifest,
)


def _manifest_with_group(members: list[dict[str, object]], group_id: int = 0) -> dict[str, object]:
    return {
        "version": 1,
        "groups": [{"group_id": group_id, "variant": "resize", "members": members}],
    }


def test_validate_manifest_missing_version() -> None:
    with pytest.raises(ManifestError):
        validate_manifest({"groups": []})


def test_validate_manifest_missing_groups() -> None:
    with pytest.raises(ManifestError):
        validate_manifest({"version": 1})


def test_validate_manifest_member_missing_action() -> None:
    data = _manifest_with_group([{"path": "a.png"}])
    with pytest.raises(ManifestError):
        validate_manifest(data)


def test_validate_manifest_unknown_action() -> None:
    data = _manifest_with_group([{"path": "a.png", "action": "delete_forever"}])
    with pytest.raises(ManifestError):
        validate_manifest(data)


def test_build_apply_plan_skips_group_with_no_removals() -> None:
    data = _manifest_with_group(
        [
            {"path": "a.png", "action": "keep"},
            {"path": "b.png", "action": "keep"},
        ]
    )
    plan = build_apply_plan(data)
    assert plan.actions == []
    assert plan.skipped_groups == [0]


def test_build_apply_plan_refuses_to_empty_a_group(tmp_path: Path) -> None:
    data = _manifest_with_group(
        [
            {"path": str(tmp_path / "a.png"), "action": "delete_candidate"},
            {"path": str(tmp_path / "b.png"), "action": "delete_candidate"},
        ]
    )
    with pytest.raises(ManifestError, match="entire group"):
        build_apply_plan(data)


def test_build_apply_plan_builds_delete_actions(tmp_path: Path) -> None:
    data = _manifest_with_group(
        [
            {"path": str(tmp_path / "keep.png"), "action": "keep"},
            {"path": str(tmp_path / "dupe.png"), "action": "delete_candidate"},
        ]
    )
    plan = build_apply_plan(data)
    assert len(plan.actions) == 1
    assert plan.actions[0].kind == "delete"
    assert plan.actions[0].path == tmp_path / "dupe.png"


def test_build_apply_plan_with_trash_dir_builds_trash_actions(tmp_path: Path) -> None:
    trash_dir = tmp_path / "trash"
    data = _manifest_with_group(
        [
            {"path": str(tmp_path / "keep.png"), "action": "keep"},
            {"path": str(tmp_path / "dupe.png"), "action": "delete_candidate"},
        ]
    )
    plan = build_apply_plan(data, trash_dir=trash_dir)
    assert plan.actions[0].kind == "trash"
    assert plan.actions[0].trash_destination == trash_dir / "group_0" / "dupe.png"


def test_apply_plan_dry_run_does_not_touch_filesystem(tmp_path: Path) -> None:
    victim = tmp_path / "dupe.png"
    victim.write_bytes(b"fake image bytes")
    data = _manifest_with_group(
        [
            {"path": str(tmp_path / "keep.png"), "action": "keep"},
            {"path": str(victim), "action": "delete_candidate"},
        ]
    )
    plan = build_apply_plan(data)
    log = apply_plan(plan, execute=False)
    assert victim.exists()
    assert any("WOULD DELETE" in line for line in log)


def test_apply_plan_execute_deletes_file(tmp_path: Path) -> None:
    victim = tmp_path / "dupe.png"
    victim.write_bytes(b"fake image bytes")
    data = _manifest_with_group(
        [
            {"path": str(tmp_path / "keep.png"), "action": "keep"},
            {"path": str(victim), "action": "delete_candidate"},
        ]
    )
    plan = build_apply_plan(data)
    apply_plan(plan, execute=True)
    assert not victim.exists()


def test_apply_plan_execute_moves_file_to_trash(tmp_path: Path) -> None:
    victim = tmp_path / "dupe.png"
    victim.write_bytes(b"fake image bytes")
    trash_dir = tmp_path / "trash"
    data = _manifest_with_group(
        [
            {"path": str(tmp_path / "keep.png"), "action": "keep"},
            {"path": str(victim), "action": "delete_candidate"},
        ]
    )
    plan = build_apply_plan(data, trash_dir=trash_dir)
    apply_plan(plan, execute=True)
    assert not victim.exists()
    assert (trash_dir / "group_0" / "dupe.png").exists()


def test_apply_plan_skips_missing_file_gracefully(tmp_path: Path) -> None:
    data = _manifest_with_group(
        [
            {"path": str(tmp_path / "keep.png"), "action": "keep"},
            {"path": str(tmp_path / "already_gone.png"), "action": "delete_candidate"},
        ]
    )
    plan = build_apply_plan(data)
    log = apply_plan(plan, execute=True)
    assert any("SKIP" in line for line in log)


def test_load_manifest_round_trip(tmp_path: Path) -> None:
    data = _manifest_with_group(
        [
            {"path": "a.png", "action": "keep"},
            {"path": "b.png", "action": "delete_candidate"},
        ]
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    loaded = load_manifest(manifest_path)
    assert loaded == data


def test_multiple_groups_only_offending_one_raises(tmp_path: Path) -> None:
    data = {
        "version": 1,
        "groups": [
            {
                "group_id": 0,
                "members": [
                    {"path": str(tmp_path / "keep0.png"), "action": "keep"},
                    {"path": str(tmp_path / "dupe0.png"), "action": "delete_candidate"},
                ],
            },
            {
                "group_id": 1,
                "members": [
                    {"path": str(tmp_path / "dupe1a.png"), "action": "delete_candidate"},
                    {"path": str(tmp_path / "dupe1b.png"), "action": "delete_candidate"},
                ],
            },
        ],
    }
    with pytest.raises(ManifestError):
        build_apply_plan(data)
