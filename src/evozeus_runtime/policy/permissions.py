from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class PermissionDeclaration(BaseModel):
    files_read: list[Path] = Field(default_factory=list)
    files_written: list[Path] = Field(default_factory=list)
    env_read: list[str] = Field(default_factory=list)
    external_commands: list[str] = Field(default_factory=list)
    network_enabled: bool = False
    network_reason: str = ""


class PermissionDecision(BaseModel):
    ok: bool
    reason: str = ""


class PermissionGate:
    def __init__(self, *, allow_network: bool = False, allow_external_commands: bool = False):
        self.allow_network = allow_network
        self.allow_external_commands = allow_external_commands

    def approve(self, declaration: PermissionDeclaration) -> PermissionDecision:
        if declaration.network_enabled and not self.allow_network:
            return PermissionDecision(ok=False, reason="network access requires explicit approval")
        if declaration.external_commands and not self.allow_external_commands:
            return PermissionDecision(ok=False, reason="external commands require explicit approval")
        return PermissionDecision(ok=True)

