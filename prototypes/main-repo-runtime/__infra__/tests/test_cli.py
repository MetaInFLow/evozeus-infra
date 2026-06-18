import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from evozeus.cli import app


runner = CliRunner()


def test_status_command_reports_manual_mode():
    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "manual-session-review" in result.output


def test_tui_dry_run_lists_core_menu_items():
    result = runner.invoke(app, ["tui", "--dry-run"])

    assert result.exit_code == 0
    assert "Current Session" in result.output
    assert "Factor Runtime" in result.output


def test_doctor_classifies_evidence_when_provided():
    result = runner.invoke(app, ["doctor", "--evidence", "fatal: network timeout"])

    assert result.exit_code == 0
    assert "network" in result.output


def test_onboard_initializes_workspace_and_factor_routes(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["onboard"])
    workspace = tmp_path / ".evozeus"
    db_path = workspace / "runtime" / "index" / "results.sqlite3"

    assert result.exit_code == 0, result.output
    assert (workspace / "config.json").exists()
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        factor_count = conn.execute("SELECT count(*) FROM installed_factors").fetchone()[0]
        route_count = conn.execute("SELECT count(*) FROM factor_result_routes").fetchone()[0]
    assert factor_count >= 8
    assert route_count > 0
    assert ".evozeus" in result.output
    assert "results.sqlite3" in result.output


def test_check_accepts_valid_branch_name():
    result = runner.invoke(app, ["check", "--branch", "codex/dev/20260615-runtime-factor-slice"])

    assert result.exit_code == 0
    assert "branch: ok" in result.output


def test_check_accepts_infra_component_branch_name():
    result = runner.invoke(app, ["check", "--branch", "codex/refactor/20260616-infra-python-package"])

    assert result.exit_code == 0
    assert "branch: ok" in result.output


def test_check_rejects_invalid_branch_name():
    result = runner.invoke(app, ["check", "--branch", "update_docs"])

    assert result.exit_code == 1
    assert "codex/<type>/<yyyymmdd>-<component>-<short-summary>" in result.output


def test_check_rejects_invalid_calendar_date():
    result = runner.invoke(app, ["check", "--branch", "codex/dev/20261332-runtime-factor-slice"])

    assert result.exit_code == 1
    assert "branch date must be a valid yyyymmdd" in result.output
