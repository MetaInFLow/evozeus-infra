from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


LEGACY_TABLES = [
    "schema_meta",
    "source_refs",
    "sessions",
    "session_events",
    "analysis_runs",
    "factor_results",
    "factor_tags",
    "event_factor_tags",
    "factor_evidence",
    "factor_datasets",
    "factor_presentations",
    "factor_run_index",
    "factor_result_latest",
    "factor_run_errors",
    "installed_factors",
    "factor_capabilities",
    "factor_result_routes",
]


class LegacySqliteLedger:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        if not self.db_path.exists():
            raise FileNotFoundError(f"legacy SQLite ledger not found: {self.db_path}")

    def table_exists(self, table: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
        return row is not None

    def rows(self, table: str) -> list[dict[str, Any]]:
        if not self.table_exists(table):
            return []
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        return [dict(row) for row in rows]

    def count(self, table: str) -> int:
        if not self.table_exists(table):
            return 0
        with self._connect() as conn:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    def counts(self) -> dict[str, int]:
        return {table: self.count(table) for table in LEGACY_TABLES}

    def schema_version(self) -> str:
        if not self.table_exists("schema_meta"):
            return ""
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
        return str(row["value"]) if row is not None else ""

    def session_by_id(self) -> dict[str, dict[str, Any]]:
        return {str(row.get("session_id") or ""): row for row in self.rows("sessions")}

    def event_by_key(self) -> dict[tuple[str, str], dict[str, Any]]:
        return {
            (str(row.get("session_id") or ""), str(row.get("event_id") or "")): row
            for row in self.rows("session_events")
        }

    def required_event_keys(self) -> set[tuple[str, str]]:
        keys: set[tuple[str, str]] = set()
        for row in self.rows("factor_evidence"):
            _add_key(keys, row.get("session_id"), row.get("event_id"))
        for row in self.rows("event_factor_tags"):
            _add_key(keys, row.get("session_id"), row.get("event_id"))
        for row in self.rows("factor_datasets"):
            session_id = str(row.get("session_id") or "")
            for record in json_array(str(row.get("records_json") or "[]")):
                if not isinstance(record, dict):
                    continue
                for key in ("event_id", "evidence_event_id"):
                    _add_key(keys, session_id, record.get(key))
                sample_event_ids = record.get("sample_event_ids")
                if isinstance(sample_event_ids, list):
                    for event_id in sample_event_ids:
                        _add_key(keys, session_id, event_id)
        return keys

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn


def _add_key(keys: set[tuple[str, str]], session_id: Any, event_id: Any) -> None:
    clean_session_id = str(session_id or "")
    clean_event_id = str(event_id or "")
    if clean_session_id and clean_event_id:
        keys.add((clean_session_id, clean_event_id))


def json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def json_array(value: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []
