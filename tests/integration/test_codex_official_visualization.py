from pathlib import Path

from evozeus_runtime.use_cases.run_codex_official_visualization import run_codex_official_visualization


def test_run_codex_official_visualization_scans_runs_and_renders_html(monkeypatch, tmp_path):
    home = tmp_path / "home"
    source = home / ".codex" / "sessions"
    source.mkdir(parents=True)
    fixture = Path("tests/fixtures/codex_sessions/session-minimal.jsonl")
    (source / "session-minimal.jsonl").write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    result = run_codex_official_visualization(
        workspace_root=tmp_path / "workspace",
        official_repo_root=_official_repo_root(),
        force=True,
    )

    assert result.session_count == 1
    assert result.factor_count == 7
    assert result.ran_count == 7
    assert result.error_count == 0
    assert result.html_path.exists()
    html = result.html_path.read_text(encoding="utf-8")
    assert "Global Canvas" in html
    assert "session-minimal" in html
    assert "official.tool-failure-frequency" in html


def _official_repo_root() -> Path:
    return Path(__file__).resolve().parents[3] / "evozeus-session-signal-skill"
