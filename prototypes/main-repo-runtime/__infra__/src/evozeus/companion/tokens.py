from __future__ import annotations

import secrets


def create_one_time_token() -> str:
    return secrets.token_urlsafe(24)


def token_matches(expected: str, provided: str | None) -> bool:
    return bool(provided) and secrets.compare_digest(expected, provided)
