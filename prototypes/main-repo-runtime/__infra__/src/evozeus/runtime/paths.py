from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    workspace_root: Path

    @classmethod
    def for_workspace(cls, workspace_root: Path) -> RuntimePaths:
        return cls(workspace_root=workspace_root)

    @property
    def state_root(self) -> Path:
        return self.workspace_root / ".evozeus"

    @property
    def runtime_root(self) -> Path:
        return self.state_root / "runtime"

    @property
    def sessions_root(self) -> Path:
        return self.state_root / "sessions"

    @property
    def logs_dir(self) -> Path:
        return self.state_root / "logs"

    @property
    def factors_runtime_dir(self) -> Path:
        return self.runtime_root / "factors"

    @property
    def installed_factors_dir(self) -> Path:
        return self.factors_runtime_dir / "installed"

    @property
    def scanners_runtime_dir(self) -> Path:
        return self.runtime_root / "scanners"

    @property
    def installed_scanners_dir(self) -> Path:
        return self.scanners_runtime_dir / "installed"

    @property
    def runtime_index_dir(self) -> Path:
        return self.runtime_root / "index"

    @property
    def companion_runtime_dir(self) -> Path:
        return self.runtime_root / "companion"

    @property
    def result_index_db(self) -> Path:
        return self.runtime_index_dir / "results.sqlite3"

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_root / session_id

    def factor_pack_dir(self, factor_id: str, version: str) -> Path:
        return self.installed_factors_dir / factor_id / version

    def scanner_pack_dir(self, provider: str, version: str) -> Path:
        return self.installed_scanners_dir / provider / version

    def ensure(self) -> RuntimePaths:
        for path in (
            self.installed_factors_dir,
            self.installed_scanners_dir,
            self.runtime_index_dir,
            self.companion_runtime_dir,
            self.sessions_root,
            self.logs_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        return self
