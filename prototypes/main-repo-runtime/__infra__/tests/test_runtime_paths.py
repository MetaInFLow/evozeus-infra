from pathlib import Path

from evozeus.runtime.paths import RuntimePaths


def test_runtime_paths_keep_downloaded_assets_outside_main_code(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path).ensure()

    assert paths.state_root == tmp_path / ".evozeus"
    assert paths.runtime_root == tmp_path / ".evozeus" / "runtime"
    assert paths.installed_factors_dir == tmp_path / ".evozeus" / "runtime" / "factors" / "installed"
    assert paths.installed_scanners_dir == tmp_path / ".evozeus" / "runtime" / "scanners" / "installed"
    assert paths.session_dir("ezs_001") == tmp_path / ".evozeus" / "sessions" / "ezs_001"
    assert (
        paths.factor_pack_dir("community.github_network_debug", "0.1.0")
        == tmp_path
        / ".evozeus"
        / "runtime"
        / "factors"
        / "installed"
        / "community.github_network_debug"
        / "0.1.0"
    )
    assert (
        paths.scanner_pack_dir("codex", "0.1.0")
        == tmp_path / ".evozeus" / "runtime" / "scanners" / "installed" / "codex" / "0.1.0"
    )

    assert paths.installed_factors_dir.is_dir()
    assert paths.installed_scanners_dir.is_dir()


def test_runtime_paths_include_logs_and_companion(tmp_path: Path):
    paths = RuntimePaths.for_workspace(tmp_path)

    assert paths.logs_dir == tmp_path / ".evozeus" / "logs"
    assert paths.companion_runtime_dir == tmp_path / ".evozeus" / "runtime" / "companion"
