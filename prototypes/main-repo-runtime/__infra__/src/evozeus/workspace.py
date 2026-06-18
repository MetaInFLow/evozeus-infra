from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from evozeus.runtime.paths import RuntimePaths


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    @property
    def drafts_dir(self) -> Path:
        return self.root / "drafts"

    @property
    def factors_dir(self) -> Path:
        return self.root / "runtime" / "factors"

    @property
    def scanners_dir(self) -> Path:
        return self.root / "runtime" / "scanners"

    @property
    def history_dir(self) -> Path:
        return self.root / "history"


def detect_workspace(cwd: Path) -> Workspace | None:
    root = cwd / ".evozeus"
    if root.exists() and root.is_dir():
        return Workspace(root=root)
    return None


def create_workspace(cwd: Path) -> Workspace:
    root = cwd / ".evozeus"
    workspace = Workspace(root=root)
    RuntimePaths.for_workspace(cwd).ensure()
    config = {
        "schema_version": "workspace_config.v0",
        "workspace_id": f"ewk_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "mode": "local_manual",
        "privacy": {
            "upload_default": False,
            "redaction_required_for_export": True,
        },
        "scan": {
            "providers": ["codex"],
            "auto_load_events": True,
        },
        "companion": {
            "host": "127.0.0.1",
            "port": 0,
        },
    }
    (root / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return workspace
