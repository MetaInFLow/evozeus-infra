from __future__ import annotations

from enum import StrEnum


class FailureKind(StrEnum):
    TOOL_PATH = "tool_path"
    AUTH = "auth"
    NETWORK = "network"
    PERMISSION = "permission"
    SKILL = "skill"
    WORKFLOW = "workflow"
    UNKNOWN = "unknown"


def classify_failure(text: str) -> FailureKind:
    lowered = text.lower()
    if "command not found" in lowered or "no such file or directory" in lowered:
        return FailureKind.TOOL_PATH
    if "unauthorized" in lowered or "authentication" in lowered or "forbidden" in lowered:
        return FailureKind.AUTH
    if "timeout" in lowered or "network" in lowered or "could not resolve host" in lowered:
        return FailureKind.NETWORK
    if "permission denied" in lowered or "operation not permitted" in lowered:
        return FailureKind.PERMISSION
    if "skill" in lowered and ("missing" in lowered or "failed" in lowered):
        return FailureKind.SKILL
    if "unclear requirement" in lowered or "needs clarification" in lowered:
        return FailureKind.WORKFLOW
    return FailureKind.UNKNOWN
