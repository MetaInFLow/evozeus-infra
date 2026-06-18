import json
from pathlib import Path

from evozeus.workspace import create_workspace, detect_workspace


def test_detect_workspace_returns_none_when_missing(tmp_path):
    assert detect_workspace(tmp_path) is None


def test_create_workspace_initializes_minimal_runtime(tmp_path: Path):
    workspace = create_workspace(tmp_path)

    assert workspace.root == tmp_path / ".evozeus"
    assert (workspace.root / "config.json").exists()
    assert (workspace.root / "runtime" / "index").is_dir()
    assert (workspace.root / "runtime" / "factors" / "installed").is_dir()
    assert (workspace.root / "runtime" / "scanners" / "installed").is_dir()
    assert (workspace.root / "runtime" / "companion").is_dir()
    assert (workspace.root / "sessions").is_dir()
    assert (workspace.root / "logs").is_dir()
    assert not (workspace.root / "drafts").exists()
    assert not (workspace.root / "history").exists()


def test_create_workspace_writes_local_first_config(tmp_path: Path):
    workspace = create_workspace(tmp_path)
    config = json.loads((workspace.root / "config.json").read_text(encoding="utf-8"))

    assert config["schema_version"] == "workspace_config.v0"
    assert config["workspace_id"].startswith("ewk_")
    assert config["created_at"]
    assert config["mode"] == "local_manual"
    assert config["privacy"]["upload_default"] is False
    assert config["privacy"]["redaction_required_for_export"] is True
    assert config["scan"]["providers"] == ["codex"]
    assert config["scan"]["auto_load_events"] is True
    assert config["companion"]["host"] == "127.0.0.1"
    assert config["companion"]["port"] == 0
