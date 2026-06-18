from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime

ALLOWED_BRANCH_TYPES = ("dev", "bug", "refactor", "docs", "test", "chore")
ALLOWED_BRANCH_COMPONENTS = (
    "runtime",
    "factor",
    "infra",
    "verdict-card",
    "doctor",
    "tui",
    "companion",
    "workspace",
    "docs",
    "governance",
    "skill",
)

BRANCH_PATTERN = re.compile(r"^codex/([a-z]+)/([0-9]{8})-([a-z0-9-]+)$")


@dataclass(frozen=True)
class BranchCheckResult:
    ok: bool
    message: str


def current_branch_name() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate_branch_name(branch_name: str) -> BranchCheckResult:
    match = BRANCH_PATTERN.fullmatch(branch_name)
    if not match:
        return BranchCheckResult(
            ok=False,
            message="branch must match codex/<type>/<yyyymmdd>-<component>-<short-summary>",
        )

    branch_type, date_stamp, tail = match.groups()
    if branch_type not in ALLOWED_BRANCH_TYPES:
        types = ", ".join(ALLOWED_BRANCH_TYPES)
        return BranchCheckResult(ok=False, message=f"branch type must be one of: {types}")
    if not _valid_yyyymmdd(date_stamp):
        return BranchCheckResult(ok=False, message="branch date must be a valid yyyymmdd")
    component, summary = _split_component_and_summary(tail)
    if not component:
        components = ", ".join(ALLOWED_BRANCH_COMPONENTS)
        return BranchCheckResult(ok=False, message=f"branch component must be one of: {components}")
    if not _valid_summary(summary):
        return BranchCheckResult(
            ok=False,
            message="branch summary must use lowercase kebab-case with 1-7 words",
        )

    return BranchCheckResult(ok=True, message="branch: ok")


def _valid_yyyymmdd(date_stamp: str) -> bool:
    try:
        parsed = datetime.strptime(date_stamp, "%Y%m%d")
    except ValueError:
        return False
    return parsed.strftime("%Y%m%d") == date_stamp and 2000 <= parsed.year <= 2099


def _split_component_and_summary(tail: str) -> tuple[str | None, str]:
    for component in sorted(ALLOWED_BRANCH_COMPONENTS, key=len, reverse=True):
        prefix = f"{component}-"
        if tail.startswith(prefix):
            return component, tail.removeprefix(prefix)
    return None, tail


def _valid_summary(summary: str) -> bool:
    words = summary.split("-")
    return 1 <= len(words) <= 7 and all(word.isascii() and word.isalnum() for word in words)
