"""Load, validate, and apply a reviewed manifest.

The scan command only ever writes a manifest; nothing is deleted until a
human (or an automated policy the human trusts) has reviewed it and this
module's :func:`apply_manifest` is invoked explicitly. Even then, a group
whose members are *all* marked for removal is refused -- deduplication
should never leave zero copies of an image.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ManifestError(ValueError):
    """Raised when a manifest fails validation or an apply-time safety check."""


@dataclass(frozen=True)
class ApplyAction:
    group_id: int
    path: Path
    kind: str  # "delete" or "trash"
    trash_destination: Path | None = None


@dataclass(frozen=True)
class ApplyPlan:
    actions: list[ApplyAction]
    skipped_groups: list[int]


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    validate_manifest(data)
    return data


def validate_manifest(data: dict[str, Any]) -> None:
    if "version" not in data:
        raise ManifestError("manifest missing 'version'")
    if "groups" not in data or not isinstance(data["groups"], list):
        raise ManifestError("manifest missing 'groups' list")
    for group in data["groups"]:
        if "members" not in group or not isinstance(group["members"], list):
            raise ManifestError(f"group {group.get('group_id')} missing 'members' list")
        for member in group["members"]:
            if "path" not in member or "action" not in member:
                raise ManifestError(
                    f"group {group.get('group_id')} has a member missing 'path' or 'action'"
                )
            if member["action"] not in ("keep", "delete_candidate"):
                raise ManifestError(
                    f"group {group.get('group_id')} member has unknown action "
                    f"{member['action']!r} (expected 'keep' or 'delete_candidate')"
                )


def build_apply_plan(data: dict[str, Any], trash_dir: Path | None = None) -> ApplyPlan:
    """Validate every group's actions and build the concrete list of file
    operations to perform, without touching the filesystem.

    Refuses (raises :class:`ManifestError`) if any group would have every
    member removed -- at least one member per group must be kept.
    """
    validate_manifest(data)
    actions: list[ApplyAction] = []
    skipped: list[int] = []

    for group in data["groups"]:
        members = group["members"]
        group_id = group["group_id"]
        keep_count = sum(1 for m in members if m["action"] == "keep")
        removal_count = sum(1 for m in members if m["action"] == "delete_candidate")

        if removal_count == 0:
            skipped.append(group_id)
            continue

        if keep_count == 0:
            raise ManifestError(
                f"group {group_id} has every member marked 'delete_candidate'; "
                "refusing to remove an entire group. Mark at least one member 'keep'."
            )

        for member in members:
            if member["action"] != "delete_candidate":
                continue
            src = Path(member["path"])
            if trash_dir is not None:
                trash_destination = trash_dir / f"group_{group_id}" / src.name
                actions.append(ApplyAction(group_id, src, "trash", trash_destination))
            else:
                actions.append(ApplyAction(group_id, src, "delete"))

    return ApplyPlan(actions=actions, skipped_groups=skipped)


def apply_plan(plan: ApplyPlan, execute: bool = False) -> list[str]:
    """Execute (or, if ``execute`` is False, just describe) an apply plan.

    Returns a list of human-readable log lines describing what happened
    (or what would happen, in dry-run mode).
    """
    log: list[str] = []
    for action in plan.actions:
        if not action.path.exists():
            log.append(f"SKIP (missing) {action.path}")
            continue
        if action.kind == "trash":
            assert action.trash_destination is not None
            log.append(f"{'MOVE' if execute else 'WOULD MOVE'} {action.path} -> {action.trash_destination}")
            if execute:
                action.trash_destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(action.path), str(action.trash_destination))
        else:
            log.append(f"{'DELETE' if execute else 'WOULD DELETE'} {action.path}")
            if execute:
                action.path.unlink()
    return log
