from __future__ import annotations

import json
from pathlib import Path

from img_dedupe.cli import main
from tests.imgen import pattern_image, save


def test_cli_scan_writes_manifest(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    img = pattern_image(seed=1, size=(120, 120))
    save(img, tmp_path / "a.png")
    save(img, tmp_path / "b.png")

    manifest_path = tmp_path / "manifest.json"
    exit_code = main(["scan", str(tmp_path), "-o", str(manifest_path)])

    assert exit_code == 0
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["summary"]["total_images"] == 2
    assert data["summary"]["duplicate_groups"] == 1

    out = capsys.readouterr().out
    assert "Scanned 2 image(s)" in out


def test_cli_scan_missing_directory_errors(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    exit_code = main(["scan", str(missing)])
    assert exit_code == 2


def test_cli_apply_dry_run_then_execute(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    img = pattern_image(seed=2, size=(100, 100))
    save(img, tmp_path / "a.png")
    save(img, tmp_path / "b.png")

    manifest_path = tmp_path / "manifest.json"
    main(["scan", str(tmp_path), "-o", str(manifest_path)])

    data = json.loads(manifest_path.read_text())
    removal_paths = [
        m["path"] for g in data["groups"] for m in g["members"] if m["action"] == "delete_candidate"
    ]
    assert len(removal_paths) == 1
    victim = Path(removal_paths[0])
    assert victim.exists()

    # Dry run: nothing removed yet.
    exit_code = main(["apply", str(manifest_path)])
    assert exit_code == 0
    assert victim.exists()
    out = capsys.readouterr().out
    assert "Dry run" in out

    # Execute: file actually removed.
    exit_code = main(["apply", str(manifest_path), "--execute"])
    assert exit_code == 0
    assert not victim.exists()


def test_cli_apply_with_trash_dir(tmp_path: Path) -> None:
    img = pattern_image(seed=3, size=(100, 100))
    save(img, tmp_path / "a.png")
    save(img, tmp_path / "b.png")

    manifest_path = tmp_path / "manifest.json"
    main(["scan", str(tmp_path), "-o", str(manifest_path)])

    trash_dir = tmp_path / "trash"
    exit_code = main(["apply", str(manifest_path), "--trash-dir", str(trash_dir), "--execute"])
    assert exit_code == 0
    assert trash_dir.exists()
    moved = list(trash_dir.rglob("*.png"))
    assert len(moved) == 1


def test_cli_apply_invalid_manifest_errors(tmp_path: Path) -> None:
    bad_manifest = tmp_path / "bad.json"
    bad_manifest.write_text("{not valid json")
    exit_code = main(["apply", str(bad_manifest)])
    assert exit_code == 2


def test_cli_apply_refuses_emptied_group(tmp_path: Path) -> None:
    img = pattern_image(seed=4, size=(100, 100))
    a = save(img, tmp_path / "a.png")
    b = save(img, tmp_path / "b.png")

    manifest_path = tmp_path / "manifest.json"
    main(["scan", str(tmp_path), "-o", str(manifest_path)])

    data = json.loads(manifest_path.read_text())
    # Tamper with the manifest: mark every member of the group for removal.
    for group in data["groups"]:
        for member in group["members"]:
            member["action"] = "delete_candidate"
    manifest_path.write_text(json.dumps(data))

    exit_code = main(["apply", str(manifest_path), "--execute"])
    assert exit_code == 2
    assert a.exists()
    assert b.exists()


def test_cli_scan_custom_extensions_and_strategy_order(tmp_path: Path) -> None:
    img = pattern_image(seed=5, size=(100, 100))
    save(img, tmp_path / "a.png")
    save(img, tmp_path / "b.png")

    manifest_path = tmp_path / "manifest.json"
    exit_code = main(
        [
            "scan",
            str(tmp_path),
            "-o",
            str(manifest_path),
            "--extensions",
            "png",
            "--strategy-order",
            "file_size,resolution,oldest",
            "--algorithm",
            "dhash",
        ]
    )
    assert exit_code == 0
    data = json.loads(manifest_path.read_text())
    assert data["settings"]["algorithm"] == "dhash"
    assert data["settings"]["strategy_order"] == ["file_size", "resolution", "oldest"]
