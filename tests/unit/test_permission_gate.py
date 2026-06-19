from pathlib import Path

from evozeus_runtime.policy.permissions import PermissionDeclaration, PermissionGate


def test_permission_gate_rejects_network_by_default():
    declaration = PermissionDeclaration(network_enabled=True, network_reason="download manifest")

    result = PermissionGate().approve(declaration)

    assert result.ok is False
    assert "network" in result.reason


def test_permission_gate_rejects_external_commands_by_default():
    declaration = PermissionDeclaration(external_commands=["uv sync"])

    result = PermissionGate().approve(declaration)

    assert result.ok is False
    assert "external commands" in result.reason


def test_permission_gate_accepts_declared_local_read():
    declaration = PermissionDeclaration(files_read=[Path("tests/fixtures/codex_sessions")])

    result = PermissionGate().approve(declaration)

    assert result.ok is True

