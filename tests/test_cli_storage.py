"""storage CLI contract tests."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from dochris.cli.cli_storage import cmd_storage
from dochris.cli.main import main


def _workspace_with_duplicate(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "kb"
    target_dir = workspace / "wiki/concepts"
    target_dir.mkdir(parents=True)
    (target_dir / "概念.md").write_text("# 概念\n", encoding="utf-8")
    duplicate = target_dir / "概念_1.md"
    duplicate.write_text("# 概念\n", encoding="utf-8")
    return workspace, duplicate


def test_storage_audit_can_emit_machine_readable_json(tmp_path: Path, capsys) -> None:
    workspace, duplicate = _workspace_with_duplicate(tmp_path)

    result = cmd_storage(
        Namespace(
            storage_command="audit",
            workspace=str(workspace),
            json=True,
        )
    )

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["safe_to_migrate"] == 1
    assert payload["planned_moves"][0]["duplicate"] == "wiki/concepts/概念_1.md"
    assert duplicate.exists()


def test_storage_migrate_is_dry_run_until_apply_is_explicit(tmp_path: Path, capsys) -> None:
    workspace, duplicate = _workspace_with_duplicate(tmp_path)
    backup_dir = tmp_path / "backup"

    dry_run = cmd_storage(
        Namespace(
            storage_command="migrate",
            workspace=str(workspace),
            apply=False,
            backup_dir=str(backup_dir),
            json=False,
        )
    )
    assert dry_run == 0
    assert "dry-run" in capsys.readouterr().out
    assert duplicate.exists()

    applied = cmd_storage(
        Namespace(
            storage_command="migrate",
            workspace=str(workspace),
            apply=True,
            backup_dir=str(backup_dir),
            json=False,
        )
    )
    assert applied == 0
    output = capsys.readouterr().out
    assert "已迁移 1 个" in output
    assert str(backup_dir / "manifest.json") in output
    assert not duplicate.exists()


def test_main_dispatches_storage_audit() -> None:
    with patch("dochris.cli.main.cmd_storage", return_value=0) as command:
        with patch("sys.argv", ["kb", "storage", "audit", "--json"]):
            result = main()

    assert result == 0
    args = command.call_args.args[0]
    assert args.storage_command == "audit"
    assert args.json is True
