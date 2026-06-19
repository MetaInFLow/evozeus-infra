from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_scanner_and_runner_scripts_work_together(tmp_path):
    scan = subprocess.run(
        [
            sys.executable,
            "scripts/run_scanner.py",
            "--provider",
            "codex",
            "--source",
            "tests/fixtures/codex_sessions",
            "--workspace",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert scan.returncode == 0, scan.stderr
    assert "scanned_sessions=1" in scan.stdout

    run = subprocess.run(
        [
            sys.executable,
            "scripts/run_runner.py",
            "--session-id",
            "session-minimal",
            "--factor",
            "default.tool_failure",
            "--pack-root",
            "tests/fixtures/factor_packs",
            "--workspace",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    assert "results=1" in run.stdout
    assert "errors=0" in run.stdout


def test_sqlite_visualizer_script_writes_html(tmp_path):
    scan = subprocess.run(
        [
            sys.executable,
            "scripts/run_scanner.py",
            "--provider",
            "codex",
            "--source",
            "tests/fixtures/codex_sessions",
            "--workspace",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert scan.returncode == 0, scan.stderr

    visualizer = subprocess.run(
        [
            sys.executable,
            "scripts/render_sqlite_html.py",
            "--workspace",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert visualizer.returncode == 0, visualizer.stderr
    assert "html=" in visualizer.stdout
    html_path = Path(visualizer.stdout.split("html=", 1)[1].splitlines()[0])
    assert html_path.exists()
    assert "session-minimal" in html_path.read_text(encoding="utf-8")


def test_scanner_script_uses_default_codex_dirs_when_source_is_omitted(tmp_path):
    home = tmp_path / "home"
    source = home / ".codex" / "sessions"
    source.mkdir(parents=True)
    fixture = Path("tests/fixtures/codex_sessions/session-minimal.jsonl")
    (source / "session-minimal.jsonl").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    scan = subprocess.run(
        [
            sys.executable,
            "scripts/run_scanner.py",
            "--provider",
            "codex",
            "--workspace",
            str(tmp_path / "workspace"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={"HOME": str(home)},
    )

    assert scan.returncode == 0, scan.stderr
    assert "scanned_sessions=1" in scan.stdout
