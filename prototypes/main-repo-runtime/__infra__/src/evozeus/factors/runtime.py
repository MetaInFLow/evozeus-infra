from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from pydantic import ValidationError

from evozeus.factors.base import FactorContext
from evozeus.factors.manifest import FactorRuntimeMode
from evozeus.factors.packs import FactorPack, load_factor_from_pack
from evozeus.factors.protocol import FactorResult


class FactorRuntimeError(RuntimeError):
    pass


class FactorInstallError(FactorRuntimeError):
    pass


class FactorTimeoutError(FactorRuntimeError):
    pass


class FactorInvalidResultError(FactorRuntimeError):
    pass


class UnsupportedFactorRuntimeError(FactorRuntimeError):
    pass


class RuntimeResolver:
    def __init__(self, subprocess_runtime: SubprocessUvRuntime | None = None):
        self.subprocess_runtime = subprocess_runtime or SubprocessUvRuntime()

    def run(self, pack: FactorPack, context: FactorContext) -> FactorResult:
        mode = pack.manifest.runtime.mode
        if mode == FactorRuntimeMode.IN_PROCESS:
            return load_factor_from_pack(pack).execute(context)
        if mode == FactorRuntimeMode.SUBPROCESS_UV:
            return self.subprocess_runtime.run(pack, context)
        raise UnsupportedFactorRuntimeError(f"unsupported factor runtime mode: {mode}")


class SubprocessUvRuntime:
    def run(self, pack: FactorPack, context: FactorContext) -> FactorResult:
        timeout_seconds = max(pack.manifest.runtime.timeout_ms, 1) / 1000
        python_executable = _resolve_python(pack)
        payload = {
            "session": context.session.model_dump(mode="json"),
            "config": context.config,
        }
        try:
            completed = subprocess.run(
                [
                    python_executable,
                    "-m",
                    "evozeus.factors.subprocess_worker",
                    str(pack.root),
                ],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=pack.root,
                env=_subprocess_env(),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise FactorTimeoutError(f"factor timed out after {pack.manifest.runtime.timeout_ms}ms") from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
            raise FactorRuntimeError(message)
        return _parse_factor_result(completed.stdout)


def _resolve_python(pack: FactorPack) -> str:
    runtime = pack.manifest.runtime
    dependency_file = runtime.dependency_file
    lock_file = runtime.lock_file

    if dependency_file and not (pack.root / dependency_file).is_file():
        raise FactorInstallError(f"dependency file not found: {dependency_file}")
    if lock_file and not (pack.root / lock_file).is_file():
        raise FactorInstallError(f"lock file not found: {lock_file}")

    venv_python = pack.root / ".venv" / "bin" / "python"
    if venv_python.is_file():
        return str(venv_python)

    if dependency_file or lock_file:
        _install_locked_environment(pack)
        if not venv_python.is_file():
            raise FactorInstallError("uv did not create .venv/bin/python")
        return str(venv_python)

    return sys.executable


def _install_locked_environment(pack: FactorPack) -> None:
    uv_path = shutil.which("uv")
    if uv_path is None:
        raise FactorInstallError("uv is required to install subprocess factor dependencies")

    completed = subprocess.run(
        [uv_path, "sync", "--locked", "--project", str(pack.root)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        raise FactorInstallError(message)


def _parse_factor_result(stdout: str) -> FactorResult:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise FactorInvalidResultError("subprocess factor did not return valid JSON") from exc
    try:
        return FactorResult.model_validate(payload)
    except ValidationError as exc:
        raise FactorInvalidResultError("subprocess factor returned invalid FactorResult") from exc


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    src_root = str(Path(__file__).resolve().parents[2])
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_root if not existing else f"{src_root}{os.pathsep}{existing}"
    return env
