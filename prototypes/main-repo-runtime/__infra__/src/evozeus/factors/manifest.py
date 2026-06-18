from __future__ import annotations

import json
from pathlib import Path
from enum import StrEnum

from pydantic import BaseModel, Field

from evozeus.factors.protocol import FactorSpec


class FactorRuntimeMode(StrEnum):
    IN_PROCESS = "in_process"
    SUBPROCESS_UV = "subprocess_uv"
    CONTAINER = "container"
    REMOTE = "remote"


class FactorRuntimeConfig(BaseModel):
    mode: FactorRuntimeMode = FactorRuntimeMode.IN_PROCESS
    python: str | None = None
    dependency_file: str | None = None
    lock_file: str | None = None
    timeout_ms: int = 1000


class FactorManifest(FactorSpec):
    schema_version: str = "factor.v0"
    version: str
    status: str
    description: str
    entrypoint: str = ""
    permissions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    rollback: str
    runtime: FactorRuntimeConfig = Field(default_factory=FactorRuntimeConfig)
    compatibility: dict[str, str] = Field(default_factory=dict)
    network: bool = False
    run: dict[str, str | int] = Field(default_factory=dict)


def load_manifest(path: Path) -> FactorManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return FactorManifest.model_validate(data)
