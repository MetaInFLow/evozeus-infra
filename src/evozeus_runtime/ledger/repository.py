from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from evozeus_runtime.sessions.schema import SessionEnvelope
from evozeus_runtime.factors.protocol import FactorResult
from evozeus_runtime.sessions.schema import SessionEvent
from evozeus_runtime.ledger.paths import RuntimePaths
from evozeus_runtime.scanners.base import SessionMessageRef, SessionRef


SCHEMA_VERSION = "result_store.v0"


@dataclass(frozen=True)
class SessionAnalysisStatus:
    session_id: str
    provider: str
    project_key: str
    project_label: str
    source_ref: str
    event_count: int
    discovered_at: str
    last_analyzed_at: str
    analyzed_factor_count: int
    pending_factor_count: int
    first_user_preview: str = ""
    first_user_source_ref: str = ""
    first_user_source_line: int = 0
    last_assistant_preview: str = ""
    last_assistant_source_ref: str = ""
    last_assistant_source_line: int = 0
    stale_reason: str = ""
    session_title: str = ""
    session_cwd: str = ""
    session_group_key: str = ""
    session_group_label: str = ""
    session_updated_at: str = ""


@dataclass(frozen=True)
class EventFactorTag:
    session_id: str
    event_id: str
    event_index: int
    role: str
    content: str
    factor_id: str
    tag_type: str
    tag_value: str
    result_run_id: str
    analysis_run_id: str
    last_run_at: str


@dataclass(frozen=True)
class SessionEventTag:
    factor_id: str
    tag_type: str
    tag_value: str
    reason: str
    result_run_id: str
    analysis_run_id: str
    last_run_at: str


@dataclass(frozen=True)
class SessionEventRecord:
    session_id: str
    event_id: str
    event_index: int
    role: str
    content: str
    tool_name: str
    tool_result_preview: str
    source_ref: str
    source_line: int
    tags: list[SessionEventTag]


@dataclass(frozen=True)
class InstalledFactor:
    factor_id: str
    version: str
    source: str
    installed_at: str
    enabled: bool
    runtime_mode: str
    status: str
    supported_providers: list[str]
    supported_target_types: list[str]


@dataclass(frozen=True)
class FactorResultRoute:
    factor_id: str
    result_type: str
    route_area: str
    route_key: str
    component: str
    title: str
    priority: int
    enabled: bool


class LedgerRepository:
    def __init__(self, paths: RuntimePaths):
        self.paths = paths
        self.db_path = paths.result_index_db
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def record_session_refs(self, refs: Iterable[SessionRef]) -> None:
        now = _utc_now()
        with self._connect() as conn:
            for ref in refs:
                metadata = {**(ref.metadata or {}), "source_ref": str(ref.source_path)}
                conn.execute(
                    """
                    INSERT INTO source_refs (
                        provider, source_ref, source_size, source_mtime,
                        source_fingerprint, last_seen_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(provider, source_ref) DO UPDATE SET
                        source_size = excluded.source_size,
                        source_mtime = excluded.source_mtime,
                        source_fingerprint = excluded.source_fingerprint,
                        last_seen_at = excluded.last_seen_at
                    """,
                    (
                        ref.provider,
                        str(ref.source_path),
                        _int(metadata.get("source_size"), default=0),
                        str(metadata.get("source_mtime") or ""),
                        str(metadata.get("source_fingerprint") or ""),
                        now,
                    ),
                )
                _delete_session_source_aliases(
                    conn,
                    provider=ref.provider,
                    source_ref=str(ref.source_path),
                    keep_session_id=ref.session_id,
                )
                conn.execute(
                    """
                    INSERT INTO sessions (
                        session_id, provider, project_key, project_label, source_ref,
                        discovered_at, first_seen_at, last_seen_at, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        provider = excluded.provider,
                        project_key = excluded.project_key,
                        project_label = excluded.project_label,
                        source_ref = excluded.source_ref,
                        last_seen_at = excluded.last_seen_at,
                        metadata_json = excluded.metadata_json
                    """,
                    (
                        ref.session_id,
                        ref.provider,
                        _project_key(metadata),
                        _project_label(metadata),
                        str(ref.source_path),
                        now,
                        now,
                        now,
                        _json(metadata),
                    ),
                )

    def record_session_message_refs(self, refs: Iterable[SessionMessageRef]) -> None:
        with self._connect() as conn:
            counts_by_session: dict[str, int] = {}
            for ref in refs:
                counts_by_session[ref.session_id] = max(counts_by_session.get(ref.session_id, 0), ref.message_index)
                conn.execute(
                    """
                    INSERT INTO session_events (
                        session_id, event_id, event_index, provider, scanner_id, scanner_version,
                        role, tool_name, source_ref, source_fingerprint, event_locator_json,
                        artifact_locator_json, content_hash, content_preview_redacted,
                        tool_result_hash, tool_result_preview_redacted, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', '', '', ?)
                    ON CONFLICT(session_id, event_id) DO UPDATE SET
                        event_index = excluded.event_index,
                        provider = excluded.provider,
                        scanner_id = excluded.scanner_id,
                        scanner_version = excluded.scanner_version,
                        role = excluded.role,
                        tool_name = excluded.tool_name,
                        source_ref = excluded.source_ref,
                        source_fingerprint = excluded.source_fingerprint,
                        event_locator_json = excluded.event_locator_json,
                        artifact_locator_json = excluded.artifact_locator_json,
                        metadata_json = excluded.metadata_json
                    """,
                    (
                        ref.session_id,
                        ref.message_id,
                        ref.message_index,
                        ref.provider,
                        str(ref.metadata.get("scanner_id") or ""),
                        str(ref.metadata.get("scanner_version") or ""),
                        str(ref.metadata.get("role") or ""),
                        str(ref.metadata.get("tool_name") or ""),
                        str(ref.metadata.get("source_ref") or ref.source_path),
                        str(ref.metadata.get("source_fingerprint") or ""),
                        str(ref.metadata.get("event_locator_json") or "{}"),
                        "{}",
                        _json(_compact_event_metadata(ref.metadata)),
                    ),
                )
            for session_id, event_count in counts_by_session.items():
                conn.execute(
                    """
                    UPDATE sessions
                    SET event_count = ?
                    WHERE session_id = ?
                    """,
                    (event_count, session_id),
                )

    def record_session_envelope(self, session: SessionEnvelope) -> None:
        now = _utc_now()
        with self._connect() as conn:
            self._upsert_session(conn, session, now)
            self._upsert_events(conn, session)

    def record_installed_factors(self, packs: Iterable[Any], *, source: str) -> None:
        now = _utc_now()
        with self._connect() as conn:
            for pack in packs:
                manifest = pack.manifest
                factor_id = str(manifest.id)
                version = str(manifest.version)
                runtime_mode = str(manifest.runtime.mode)
                if "." in runtime_mode:
                    runtime_mode = runtime_mode.rsplit(".", 1)[-1]
                runtime_mode = getattr(manifest.runtime.mode, "value", runtime_mode)
                conn.execute(
                    """
                    INSERT INTO installed_factors (
                        factor_id, version, source, installed_at, enabled,
                        runtime_mode, manifest_path, factor_xml_path, status, status_message
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '')
                    ON CONFLICT(factor_id, version) DO UPDATE SET
                        source = excluded.source,
                        enabled = excluded.enabled,
                        runtime_mode = excluded.runtime_mode,
                        manifest_path = excluded.manifest_path,
                        factor_xml_path = excluded.factor_xml_path,
                        status = excluded.status,
                        status_message = excluded.status_message
                    """,
                    (
                        factor_id,
                        version,
                        source,
                        now,
                        1,
                        str(runtime_mode),
                        str(pack.root / "factor.json"),
                        str(pack.root / "FACTOR.xml"),
                        "available",
                    ),
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO factor_capabilities (
                        factor_id, version, provider, target_type, supported, reason
                    )
                    VALUES (?, ?, 'codex', 'session', 1, '')
                    """,
                    (factor_id, version),
                )

    def list_installed_factors(self) -> list[InstalledFactor]:
        with self._connect() as conn:
            factor_rows = conn.execute(
                """
                SELECT factor_id, version, source, installed_at, enabled, runtime_mode, status
                FROM installed_factors
                ORDER BY factor_id, version
                """
            ).fetchall()
            capability_rows = conn.execute(
                """
                SELECT factor_id, version, provider, target_type
                FROM factor_capabilities
                WHERE supported = 1
                ORDER BY factor_id, version, provider, target_type
                """
            ).fetchall()

        providers_by_factor: dict[tuple[str, str], list[str]] = {}
        targets_by_factor: dict[tuple[str, str], list[str]] = {}
        for row in capability_rows:
            key = (str(row["factor_id"]), str(row["version"]))
            providers_by_factor.setdefault(key, [])
            targets_by_factor.setdefault(key, [])
            provider = str(row["provider"])
            target_type = str(row["target_type"])
            if provider not in providers_by_factor[key]:
                providers_by_factor[key].append(provider)
            if target_type not in targets_by_factor[key]:
                targets_by_factor[key].append(target_type)

        factors: list[InstalledFactor] = []
        for row in factor_rows:
            key = (str(row["factor_id"]), str(row["version"]))
            factors.append(
                InstalledFactor(
                    factor_id=key[0],
                    version=key[1],
                    source=str(row["source"]),
                    installed_at=str(row["installed_at"]),
                    enabled=bool(row["enabled"]),
                    runtime_mode=str(row["runtime_mode"]),
                    status=str(row["status"]),
                    supported_providers=providers_by_factor.get(key, []),
                    supported_target_types=targets_by_factor.get(key, []),
                )
            )
        return factors

    def record_default_routes(self, packs: Iterable[Any]) -> None:
        with self._connect() as conn:
            for pack in packs:
                factor_id = str(pack.manifest.id)
                title = str(pack.introduction.name)
                routes = [
                    ("factor_result", "drawer", "factor_result", "factor_result_detail", title, 100),
                    ("factor_tags", "sessions_table", "factor_tags", "factor_tag_column", title, 100),
                    (
                        "factor_dashboard",
                        "dashboard",
                        _dashboard_route_key(factor_id),
                        _dashboard_component(factor_id),
                        title,
                        _dashboard_priority(factor_id),
                    ),
                ]
                for result_type, route_area, route_key, component, route_title, priority in routes:
                    conn.execute(
                        """
                        INSERT INTO factor_result_routes (
                            factor_id, result_type, route_area, route_key,
                            component, title, priority, enabled
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                        ON CONFLICT(factor_id, route_area, route_key) DO UPDATE SET
                            result_type = excluded.result_type,
                            component = excluded.component,
                            title = excluded.title,
                            priority = excluded.priority,
                            enabled = excluded.enabled
                        """,
                        (factor_id, result_type, route_area, route_key, component, route_title, priority),
                    )

    def list_factor_result_routes(self) -> list[FactorResultRoute]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT factor_id, result_type, route_area, route_key, component, title, priority, enabled
                FROM factor_result_routes
                WHERE enabled = 1
                ORDER BY route_area, priority, factor_id, route_key
                """
            ).fetchall()
        return [
            FactorResultRoute(
                factor_id=str(row["factor_id"]),
                result_type=str(row["result_type"]),
                route_area=str(row["route_area"]),
                route_key=str(row["route_key"]),
                component=str(row["component"]),
                title=str(row["title"]),
                priority=int(row["priority"]),
                enabled=bool(row["enabled"]),
            )
            for row in rows
        ]

    def record_factor_run(
        self,
        session: SessionEnvelope,
        results: list[FactorResult],
        *,
        factor_ids: Iterable[str] | None = None,
        errors: Iterable[Any] | None = None,
    ) -> str:
        analysis_run_id = f"arun_{uuid4().hex}"
        now = _utc_now()
        selected_factor_ids = list(factor_ids or [result.factor_id for result in results])
        error_items = list(errors or [])
        status = "error" if error_items else "completed"
        evidence_event_ids = _result_evidence_event_ids(results)
        with self._connect() as conn:
            self._upsert_session(conn, session, now)
            self._upsert_events(conn, session, event_ids=evidence_event_ids)
            conn.execute(
                """
                INSERT INTO analysis_runs (
                    analysis_run_id, session_id, provider, started_at, completed_at,
                    factor_ids_json, result_count, error_count, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_run_id,
                    session.session_id,
                    session.provider,
                    now,
                    now,
                    _json(selected_factor_ids),
                    len(results),
                    len(error_items),
                    status,
                ),
            )
            for result in results:
                self._insert_result(
                    conn,
                    analysis_run_id,
                    session.session_id,
                    result,
                    now,
                    source_fingerprint=str(session.metadata.get("source_fingerprint") or ""),
                )
            for error in error_items:
                self._insert_error(conn, analysis_run_id, session.session_id, error, now)
            self._delete_orphan_analysis_runs(conn, session.session_id)
        return analysis_run_id

    def list_session_statuses(self, *, factor_ids: Iterable[str] | None = None) -> list[SessionAnalysisStatus]:
        requested_factor_ids = list(factor_ids or [])
        with self._connect() as conn:
            session_rows = conn.execute(
                """
                SELECT
                    s.session_id,
                    s.provider,
                    s.project_key,
                    s.project_label,
                    s.source_ref,
                    s.discovered_at,
                    s.event_count,
                    s.metadata_json,
                    COALESCE(sr.source_fingerprint, '') AS source_fingerprint
                FROM sessions s
                LEFT JOIN source_refs sr
                  ON sr.provider = s.provider
                 AND sr.source_ref = s.source_ref
                ORDER BY s.session_id
                """
            ).fetchall()
            event_rows = conn.execute(
                """
                SELECT
                    session_id,
                    role,
                    event_index,
                    source_ref,
                    event_locator_json,
                    content_preview_redacted,
                    metadata_json
                FROM session_events
                WHERE role IN ('user', 'assistant')
                ORDER BY session_id, event_index
                """
            ).fetchall()
            index_rows = self._select_factor_run_index(conn, requested_factor_ids)

        runs_by_session: dict[str, list[sqlite3.Row]] = {}
        for row in index_rows:
            runs_by_session.setdefault(str(row["session_id"]), []).append(row)

        first_user_by_session: dict[str, sqlite3.Row] = {}
        last_assistant_by_session: dict[str, sqlite3.Row] = {}
        for row in event_rows:
            session_id = str(row["session_id"])
            role = str(row["role"])
            factor_channel = _event_factor_channel(row)
            if role == "user" and factor_channel == "user_input" and session_id not in first_user_by_session:
                first_user_by_session[session_id] = row
            if role == "assistant" and factor_channel in {"assistant_result", ""}:
                last_assistant_by_session[session_id] = row

        statuses: list[SessionAnalysisStatus] = []
        for row in session_rows:
            session_metadata = _json_dict(str(row["metadata_json"] or "{}"))
            session_runs = runs_by_session.get(str(row["session_id"]), [])
            first_user = first_user_by_session.get(str(row["session_id"]))
            last_assistant = last_assistant_by_session.get(str(row["session_id"]))
            first_user_ref, first_user_line = _source_locator(first_user)
            last_assistant_ref, last_assistant_line = _source_locator(last_assistant)
            analyzed_factor_ids = {str(run["factor_id"]) for run in session_runs}
            current_source_fingerprint = str(row["source_fingerprint"])
            stale_factor_ids = {
                str(run["factor_id"])
                for run in session_runs
                if current_source_fingerprint
                and str(run["source_fingerprint"])
                and str(run["source_fingerprint"]) != current_source_fingerprint
            }
            analyzed_count = len(analyzed_factor_ids)
            if requested_factor_ids:
                missing_factor_ids = set(requested_factor_ids) - analyzed_factor_ids
                pending_count = len(missing_factor_ids | stale_factor_ids)
            else:
                pending_count = 0
            last_analyzed_at = max((str(run["last_run_at"]) for run in session_runs), default="")
            statuses.append(
                SessionAnalysisStatus(
                    session_id=str(row["session_id"]),
                    provider=str(row["provider"]),
                    project_key=str(row["project_key"] or session_metadata.get("session_group_key") or ""),
                    project_label=str(row["project_label"] or session_metadata.get("session_group_label") or ""),
                    source_ref=str(row["source_ref"]),
                    event_count=int(row["event_count"]),
                    discovered_at=str(row["discovered_at"]),
                    last_analyzed_at=last_analyzed_at,
                    analyzed_factor_count=analyzed_count,
                    pending_factor_count=pending_count,
                    first_user_preview=_content_preview(first_user),
                    first_user_source_ref=first_user_ref,
                    first_user_source_line=first_user_line,
                    last_assistant_preview=_content_preview(last_assistant),
                    last_assistant_source_ref=last_assistant_ref,
                    last_assistant_source_line=last_assistant_line,
                    stale_reason="source_changed" if stale_factor_ids else "",
                    session_title=str(session_metadata.get("session_title") or ""),
                    session_cwd=str(session_metadata.get("session_cwd") or ""),
                    session_group_key=str(session_metadata.get("session_group_key") or ""),
                    session_group_label=str(session_metadata.get("session_group_label") or ""),
                    session_updated_at=str(session_metadata.get("session_updated_at") or ""),
                )
            )
        return statuses

    def list_event_factor_tags(self, *, session_id: str | None = None) -> list[EventFactorTag]:
        sql = """
            SELECT
                eft.session_id,
                eft.event_id,
                e.event_index,
                e.role,
                e.content_preview_redacted AS content,
                eft.factor_id,
                eft.tag_type,
                eft.tag_value,
                eft.result_run_id,
                eft.analysis_run_id,
                eft.last_run_at
            FROM event_factor_tags eft
            JOIN session_events e
              ON e.session_id = eft.session_id
             AND e.event_id = eft.event_id
        """
        params: list[str] = []
        if session_id is not None:
            sql += " WHERE eft.session_id = ?"
            params.append(session_id)
        sql += " ORDER BY eft.session_id, e.event_index, eft.factor_id, eft.tag_type, eft.tag_value"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            EventFactorTag(
                session_id=str(row["session_id"]),
                event_id=str(row["event_id"]),
                event_index=int(row["event_index"]),
                role=str(row["role"]),
                content=str(row["content"]),
                factor_id=str(row["factor_id"]),
                tag_type=str(row["tag_type"]),
                tag_value=str(row["tag_value"]),
                result_run_id=str(row["result_run_id"]),
                analysis_run_id=str(row["analysis_run_id"]),
                last_run_at=str(row["last_run_at"]),
            )
            for row in rows
        ]

    def list_session_events(self, *, session_id: str | None = None) -> list[SessionEventRecord]:
        event_sql = """
            SELECT
                session_id,
                event_id,
                event_index,
                role,
                tool_name,
                source_ref,
                event_locator_json,
                content_preview_redacted,
                tool_result_preview_redacted
            FROM session_events
        """
        event_params: list[str] = []
        if session_id is not None:
            event_sql += " WHERE session_id = ?"
            event_params.append(session_id)
        event_sql += " ORDER BY session_id, event_index"

        tag_sql = """
            SELECT
                session_id,
                event_id,
                factor_id,
                tag_type,
                tag_value,
                result_run_id,
                analysis_run_id,
                last_run_at
            FROM event_factor_tags
        """
        tag_params: list[str] = []
        if session_id is not None:
            tag_sql += " WHERE session_id = ?"
            tag_params.append(session_id)
        tag_sql += " ORDER BY session_id, event_id, factor_id, tag_type, tag_value"

        with self._connect() as conn:
            event_rows = conn.execute(event_sql, event_params).fetchall()
            tag_rows = conn.execute(tag_sql, tag_params).fetchall()

        tags_by_event: dict[tuple[str, str], list[SessionEventTag]] = {}
        for row in tag_rows:
            key = (str(row["session_id"]), str(row["event_id"]))
            tags_by_event.setdefault(key, []).append(
                SessionEventTag(
                    factor_id=str(row["factor_id"]),
                    tag_type=str(row["tag_type"]),
                    tag_value=str(row["tag_value"]),
                    reason="",
                    result_run_id=str(row["result_run_id"]),
                    analysis_run_id=str(row["analysis_run_id"]),
                    last_run_at=str(row["last_run_at"]),
                )
            )

        records: list[SessionEventRecord] = []
        for row in event_rows:
            source_ref, source_line = _source_locator(row)
            event_key = (str(row["session_id"]), str(row["event_id"]))
            records.append(
                SessionEventRecord(
                    session_id=event_key[0],
                    event_id=event_key[1],
                    event_index=int(row["event_index"]),
                    role=str(row["role"]),
                    content=str(row["content_preview_redacted"]),
                    tool_name=str(row["tool_name"] or ""),
                    tool_result_preview=str(row["tool_result_preview_redacted"] or ""),
                    source_ref=source_ref,
                    source_line=source_line,
                    tags=tags_by_event.get(event_key, []),
                )
            )
        return records

    def list_factor_results(self, *, session_id: str) -> list[FactorResult]:
        with self._connect() as conn:
            result_rows = conn.execute(
                """
                SELECT
                    result_run_id,
                    analysis_run_id,
                    session_id,
                    factor_id,
                    factor_version,
                    framework_id,
                    stage,
                    target_type,
                    target_id,
                    status,
                    confidence,
                    verdict_signals_json,
                    scores_json,
                    statistics_json,
                    notes_json,
                    created_at
                FROM factor_results
                WHERE session_id = ?
                ORDER BY created_at, factor_id
                """,
                (session_id,),
            ).fetchall()
            tag_rows = conn.execute(
                """
                SELECT result_run_id, tag_type, tag_value
                FROM factor_tags
                WHERE session_id = ?
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()
            evidence_rows = conn.execute(
                """
                SELECT result_run_id, evidence_json
                FROM factor_evidence
                WHERE session_id = ?
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()
            dataset_rows = conn.execute(
                """
                SELECT
                    result_run_id,
                    dataset_id,
                    semantic_type,
                    shape,
                    primary_key,
                    schema_json,
                    records_json,
                    evidence_policy_json
                FROM factor_datasets
                WHERE session_id = ?
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()
            presentation_rows = conn.execute(
                """
                SELECT
                    result_run_id,
                    presentation_id,
                    title,
                    component_ref,
                    data_ref,
                    bindings_json,
                    props_json,
                    routes_json,
                    fallback_json,
                    priority
                FROM factor_presentations
                WHERE session_id = ?
                ORDER BY id
                """,
                (session_id,),
            ).fetchall()

        tags_by_result: dict[str, list[dict[str, str]]] = {}
        for row in tag_rows:
            tags_by_result.setdefault(str(row["result_run_id"]), []).append(
                {
                    "type": str(row["tag_type"]),
                    "value": str(row["tag_value"]),
                }
            )

        evidence_by_result: dict[str, list[dict[str, str]]] = {}
        for row in evidence_rows:
            payload = _json_dict(str(row["evidence_json"] or "{}"))
            evidence_by_result.setdefault(str(row["result_run_id"]), []).append(
                {str(key): str(value) for key, value in payload.items()}
            )

        datasets_by_result: dict[str, list[dict[str, Any]]] = {}
        for row in dataset_rows:
            datasets_by_result.setdefault(str(row["result_run_id"]), []).append(
                {
                    "id": str(row["dataset_id"]),
                    "semantic_type": str(row["semantic_type"]),
                    "shape": str(row["shape"]),
                    "primary_key": str(row["primary_key"]),
                    "records": _json_array(str(row["records_json"] or "[]")),
                    "schema": _json_dict(str(row["schema_json"] or "{}")),
                    "evidence_policy": _json_dict(str(row["evidence_policy_json"] or "{}")),
                }
            )

        presentations_by_result: dict[str, list[dict[str, Any]]] = {}
        for row in presentation_rows:
            presentations_by_result.setdefault(str(row["result_run_id"]), []).append(
                {
                    "id": str(row["presentation_id"]),
                    "title": str(row["title"]),
                    "component_ref": str(row["component_ref"]),
                    "data_ref": str(row["data_ref"]),
                    "bindings": _json_dict(str(row["bindings_json"] or "{}")),
                    "props": _json_dict(str(row["props_json"] or "{}")),
                    "routes": _json_array(str(row["routes_json"] or "[]")),
                    "fallback": _json_array(str(row["fallback_json"] or "[]")),
                    "priority": int(row["priority"]),
                }
            )

        return [
            FactorResult(
                run_id=str(row["result_run_id"]),
                factor_id=str(row["factor_id"]),
                factor_version=str(row["factor_version"]),
                framework_id=str(row["framework_id"]),
                stage=str(row["stage"]),
                target_type=str(row["target_type"]),
                target_id=str(row["target_id"]),
                session_id=str(row["session_id"]),
                status=str(row["status"]),
                tags=tags_by_result.get(str(row["result_run_id"]), []),
                scores=_json_dict(str(row["scores_json"] or "{}")),
                statistics=_json_dict(str(row["statistics_json"] or "{}")),
                datasets=datasets_by_result.get(str(row["result_run_id"]), []),
                presentations=presentations_by_result.get(str(row["result_run_id"]), []),
                evidence_refs=evidence_by_result.get(str(row["result_run_id"]), []),
                verdict_signals=_json_list(str(row["verdict_signals_json"] or "[]")),
                notes=[str(item) for item in _json_array(str(row["notes_json"] or "[]"))],
                confidence=float(row["confidence"]),
            )
            for row in result_rows
        ]

    def get_session_ref(self, session_id: str) -> SessionRef:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    s.provider,
                    s.session_id,
                    s.source_ref,
                    s.metadata_json,
                    COALESCE(sr.source_size, 0) AS source_size,
                    COALESCE(sr.source_mtime, '') AS source_mtime,
                    COALESCE(sr.source_fingerprint, '') AS source_fingerprint
                FROM sessions s
                LEFT JOIN source_refs sr
                  ON sr.provider = s.provider
                 AND sr.source_ref = s.source_ref
                WHERE s.session_id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown session: {session_id}")
        metadata = _json_dict(str(row["metadata_json"] or "{}"))
        metadata.update(
            {
                "source_size": str(row["source_size"]),
                "source_mtime": str(row["source_mtime"]),
                "source_fingerprint": str(row["source_fingerprint"]),
            }
        )
        return SessionRef(
            provider=str(row["provider"]),
            session_id=str(row["session_id"]),
            source_path=Path(str(row["source_ref"])),
            metadata=metadata,
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    project_key TEXT NOT NULL DEFAULT '',
                    project_label TEXT NOT NULL DEFAULT '',
                    source_ref TEXT NOT NULL,
                    discovered_at TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    loaded_at TEXT NOT NULL DEFAULT '',
                    event_count INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS source_refs (
                    provider TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    source_size INTEGER NOT NULL DEFAULT 0,
                    source_mtime TEXT NOT NULL DEFAULT '',
                    source_fingerprint TEXT NOT NULL DEFAULT '',
                    last_seen_at TEXT NOT NULL,
                    PRIMARY KEY (provider, source_ref)
                );

                CREATE TABLE IF NOT EXISTS session_events (
                    session_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    event_index INTEGER NOT NULL,
                    provider TEXT NOT NULL DEFAULT '',
                    scanner_id TEXT NOT NULL DEFAULT '',
                    scanner_version TEXT NOT NULL DEFAULT '',
                    role TEXT NOT NULL,
                    tool_name TEXT,
                    source_ref TEXT NOT NULL DEFAULT '',
                    source_fingerprint TEXT NOT NULL DEFAULT '',
                    event_locator_json TEXT NOT NULL DEFAULT '{}',
                    artifact_locator_json TEXT NOT NULL DEFAULT '{}',
                    content_hash TEXT NOT NULL DEFAULT '',
                    content_preview_redacted TEXT NOT NULL DEFAULT '',
                    tool_result_hash TEXT NOT NULL DEFAULT '',
                    tool_result_preview_redacted TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (session_id, event_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_runs (
                    analysis_run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    factor_ids_json TEXT NOT NULL,
                    result_count INTEGER NOT NULL,
                    error_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS factor_results (
                    result_run_id TEXT PRIMARY KEY,
                    analysis_run_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    factor_id TEXT NOT NULL,
                    factor_version TEXT NOT NULL,
                    framework_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    verdict_signals_json TEXT NOT NULL,
                    scores_json TEXT NOT NULL,
                    statistics_json TEXT NOT NULL DEFAULT '{}',
                    notes_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs(analysis_run_id) ON DELETE CASCADE,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS factor_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result_run_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    factor_id TEXT NOT NULL,
                    tag_type TEXT NOT NULL,
                    tag_value TEXT NOT NULL,
                    FOREIGN KEY (result_run_id) REFERENCES factor_results(result_run_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS factor_evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result_run_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    factor_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    FOREIGN KEY (result_run_id) REFERENCES factor_results(result_run_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS factor_datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result_run_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    factor_id TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    semantic_type TEXT NOT NULL,
                    shape TEXT NOT NULL,
                    primary_key TEXT NOT NULL DEFAULT '',
                    schema_json TEXT NOT NULL DEFAULT '{}',
                    records_json TEXT NOT NULL DEFAULT '[]',
                    evidence_policy_json TEXT NOT NULL DEFAULT '{}',
                    record_count INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (result_run_id) REFERENCES factor_results(result_run_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS factor_presentations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result_run_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    factor_id TEXT NOT NULL,
                    presentation_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    component_ref TEXT NOT NULL,
                    data_ref TEXT NOT NULL,
                    bindings_json TEXT NOT NULL DEFAULT '{}',
                    props_json TEXT NOT NULL DEFAULT '{}',
                    routes_json TEXT NOT NULL DEFAULT '[]',
                    fallback_json TEXT NOT NULL DEFAULT '[]',
                    priority INTEGER NOT NULL DEFAULT 100,
                    FOREIGN KEY (result_run_id) REFERENCES factor_results(result_run_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS event_factor_tags (
                    session_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    result_run_id TEXT NOT NULL,
                    analysis_run_id TEXT NOT NULL,
                    factor_id TEXT NOT NULL,
                    tag_type TEXT NOT NULL,
                    tag_value TEXT NOT NULL,
                    last_run_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, event_id, factor_id, tag_type, tag_value),
                    FOREIGN KEY (session_id, event_id) REFERENCES session_events(session_id, event_id) ON DELETE CASCADE,
                    FOREIGN KEY (result_run_id) REFERENCES factor_results(result_run_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS factor_run_index (
                    session_id TEXT NOT NULL,
                    factor_id TEXT NOT NULL,
                    factor_version TEXT NOT NULL DEFAULT '',
                    target_type TEXT NOT NULL DEFAULT 'session',
                    target_id TEXT NOT NULL DEFAULT '',
                    source_fingerprint TEXT NOT NULL DEFAULT '',
                    factor_fingerprint TEXT NOT NULL DEFAULT '',
                    runtime_fingerprint TEXT NOT NULL DEFAULT '',
                    run_reason TEXT NOT NULL DEFAULT '',
                    stale_reason TEXT NOT NULL DEFAULT '',
                    last_run_at TEXT NOT NULL,
                    last_analysis_run_id TEXT NOT NULL,
                    last_result_run_id TEXT NOT NULL DEFAULT '',
                    last_status TEXT NOT NULL,
                    PRIMARY KEY (session_id, factor_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS factor_result_latest (
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    factor_id TEXT NOT NULL,
                    result_run_id TEXT NOT NULL,
                    analysis_run_id TEXT NOT NULL,
                    last_run_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    PRIMARY KEY (target_type, target_id, factor_id),
                    FOREIGN KEY (result_run_id) REFERENCES factor_results(result_run_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS factor_run_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_run_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    factor_id TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs(analysis_run_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS installed_factors (
                    factor_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    source TEXT NOT NULL,
                    installed_at TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    runtime_mode TEXT NOT NULL,
                    manifest_path TEXT NOT NULL DEFAULT '',
                    factor_xml_path TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    status_message TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (factor_id, version)
                );

                CREATE TABLE IF NOT EXISTS factor_capabilities (
                    factor_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    supported INTEGER NOT NULL DEFAULT 1,
                    reason TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (factor_id, version, provider, target_type),
                    FOREIGN KEY (factor_id, version) REFERENCES installed_factors(factor_id, version) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS factor_result_routes (
                    factor_id TEXT NOT NULL,
                    result_type TEXT NOT NULL,
                    route_area TEXT NOT NULL,
                    route_key TEXT NOT NULL,
                    component TEXT NOT NULL,
                    title TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 100,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (factor_id, route_area, route_key)
                );

                CREATE INDEX IF NOT EXISTS idx_event_factor_tags_session
                    ON event_factor_tags(session_id, factor_id);
                CREATE INDEX IF NOT EXISTS idx_factor_results_session
                    ON factor_results(session_id, factor_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_factor_results_analysis_run
                    ON factor_results(analysis_run_id);
                CREATE INDEX IF NOT EXISTS idx_factor_run_index_factor
                    ON factor_run_index(factor_id, last_run_at);
                CREATE INDEX IF NOT EXISTS idx_factor_datasets_session
                    ON factor_datasets(session_id, factor_id);
                CREATE INDEX IF NOT EXISTS idx_factor_datasets_result_run
                    ON factor_datasets(result_run_id);
                CREATE INDEX IF NOT EXISTS idx_factor_presentations_session
                    ON factor_presentations(session_id, factor_id);
                CREATE INDEX IF NOT EXISTS idx_factor_presentations_result_run
                    ON factor_presentations(result_run_id);
                CREATE INDEX IF NOT EXISTS idx_factor_tags_result_run
                    ON factor_tags(result_run_id);
                CREATE INDEX IF NOT EXISTS idx_factor_evidence_result_run
                    ON factor_evidence(result_run_id);
                CREATE INDEX IF NOT EXISTS idx_event_factor_tags_result_run
                    ON event_factor_tags(result_run_id);
                CREATE INDEX IF NOT EXISTS idx_factor_result_latest_result_run
                    ON factor_result_latest(result_run_id);
                CREATE INDEX IF NOT EXISTS idx_analysis_runs_session
                    ON analysis_runs(session_id);
                CREATE INDEX IF NOT EXISTS idx_factor_run_errors_analysis_run
                    ON factor_run_errors(analysis_run_id);
                """
            )
            _ensure_column(conn, "sessions", "project_key", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(conn, "sessions", "project_label", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(conn, "factor_results", "statistics_json", "TEXT NOT NULL DEFAULT '{}'")
            _ensure_column(conn, "factor_results", "notes_json", "TEXT NOT NULL DEFAULT '[]'")
            _ensure_column(conn, "factor_run_index", "target_type", "TEXT NOT NULL DEFAULT 'session'")
            _ensure_column(conn, "factor_run_index", "target_id", "TEXT NOT NULL DEFAULT ''")
            conn.execute(
                """
                INSERT INTO schema_meta (key, value)
                VALUES ('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (SCHEMA_VERSION,),
            )

    def _upsert_session(self, conn: sqlite3.Connection, session: SessionEnvelope, now: str) -> None:
        _delete_session_source_aliases(
            conn,
            provider=session.provider,
            source_ref=session.source_ref,
            keep_session_id=session.session_id,
        )
        conn.execute(
            """
            INSERT INTO sessions (
                session_id, provider, project_key, project_label, source_ref,
                discovered_at, first_seen_at, last_seen_at, loaded_at, event_count, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                provider = excluded.provider,
                project_key = excluded.project_key,
                project_label = excluded.project_label,
                source_ref = excluded.source_ref,
                last_seen_at = excluded.last_seen_at,
                loaded_at = excluded.loaded_at,
                event_count = excluded.event_count,
                metadata_json = excluded.metadata_json
            """,
            (
                session.session_id,
                session.provider,
                _project_key(session.metadata),
                _project_label(session.metadata),
                session.source_ref,
                now,
                now,
                now,
                now,
                len(session.events),
                _json(session.metadata),
            ),
        )

    def _upsert_events(
        self,
        conn: sqlite3.Connection,
        session: SessionEnvelope,
        *,
        event_ids: set[str] | None = None,
    ) -> None:
        for index, event in enumerate(session.events, start=1):
            if not _should_store_session_event(event, event_ids=event_ids):
                continue
            conn.execute(
                """
                INSERT INTO session_events (
                    session_id, event_id, event_index, provider, scanner_id, scanner_version,
                    role, tool_name, source_ref, source_fingerprint, event_locator_json,
                    artifact_locator_json, content_hash, content_preview_redacted,
                    tool_result_hash, tool_result_preview_redacted, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, event_id) DO UPDATE SET
                    event_index = excluded.event_index,
                    provider = excluded.provider,
                    scanner_id = excluded.scanner_id,
                    scanner_version = excluded.scanner_version,
                    role = excluded.role,
                    tool_name = excluded.tool_name,
                    source_ref = excluded.source_ref,
                    source_fingerprint = excluded.source_fingerprint,
                    event_locator_json = excluded.event_locator_json,
                    artifact_locator_json = excluded.artifact_locator_json,
                    content_hash = excluded.content_hash,
                    content_preview_redacted = excluded.content_preview_redacted,
                    tool_result_hash = excluded.tool_result_hash,
                    tool_result_preview_redacted = excluded.tool_result_preview_redacted,
                    metadata_json = excluded.metadata_json
                """,
                (
                    session.session_id,
                    event.event_id,
                    index,
                    str(event.metadata.get("provider") or session.provider),
                    str(event.metadata.get("scanner_id") or ""),
                    str(event.metadata.get("scanner_version") or ""),
                    event.role,
                    event.tool_name,
                    str(event.metadata.get("source_ref") or session.source_ref),
                    str(event.metadata.get("source_fingerprint") or session.metadata.get("source_fingerprint") or ""),
                    _json(event.metadata.get("event_locator_json") or {}),
                    "{}",
                    str(event.metadata.get("content_hash") or _content_hash(event.content)),
                    str(event.metadata.get("content_preview_redacted") or _preview(event.content)),
                    str(event.metadata.get("tool_result_hash") or _content_hash(_json(event.tool_result or {})) if event.tool_result else ""),
                    str(event.metadata.get("tool_result_preview_redacted") or _preview(_json(event.tool_result or {})) if event.tool_result else ""),
                    _json(_compact_event_metadata(event.metadata)),
                ),
            )

    def _insert_result(
        self,
        conn: sqlite3.Connection,
        analysis_run_id: str,
        session_id: str,
        result: FactorResult,
        now: str,
        source_fingerprint: str,
    ) -> None:
        result_session_id = result.session_id or session_id
        self._delete_previous_latest_result(conn, result)
        conn.execute(
            """
            INSERT INTO factor_results (
                result_run_id, analysis_run_id, session_id, factor_id, factor_version,
                framework_id, stage, target_type, target_id, status, confidence,
                verdict_signals_json, scores_json, statistics_json, notes_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.run_id,
                analysis_run_id,
                result_session_id,
                result.factor_id,
                result.factor_version,
                result.framework_id,
                str(result.stage),
                result.target_type,
                result.target_id,
                result.status,
                result.confidence,
                _json(result.verdict_signals),
                _json(result.scores),
                _json(result.statistics),
                _json(result.notes),
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO factor_run_index (
                session_id, factor_id, factor_version, target_type, target_id, source_fingerprint, factor_fingerprint,
                runtime_fingerprint, run_reason, stale_reason, last_run_at, last_analysis_run_id,
                last_result_run_id, last_status
            )
            VALUES (?, ?, ?, ?, ?, ?, '', '', 'manual', '', ?, ?, ?, ?)
            ON CONFLICT(session_id, factor_id) DO UPDATE SET
                factor_version = excluded.factor_version,
                target_type = excluded.target_type,
                target_id = excluded.target_id,
                source_fingerprint = excluded.source_fingerprint,
                factor_fingerprint = excluded.factor_fingerprint,
                runtime_fingerprint = excluded.runtime_fingerprint,
                run_reason = excluded.run_reason,
                stale_reason = excluded.stale_reason,
                last_run_at = excluded.last_run_at,
                last_analysis_run_id = excluded.last_analysis_run_id,
                last_result_run_id = excluded.last_result_run_id,
                last_status = excluded.last_status
            """,
            (
                result_session_id,
                result.factor_id,
                result.factor_version,
                result.target_type,
                result.target_id,
                source_fingerprint,
                now,
                analysis_run_id,
                result.run_id,
                result.status,
            ),
        )
        conn.execute(
            """
            INSERT INTO factor_result_latest (
                target_type, target_id, factor_id, result_run_id,
                analysis_run_id, last_run_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(target_type, target_id, factor_id) DO UPDATE SET
                result_run_id = excluded.result_run_id,
                analysis_run_id = excluded.analysis_run_id,
                last_run_at = excluded.last_run_at,
                status = excluded.status
            """,
            (
                result.target_type,
                result.target_id,
                result.factor_id,
                result.run_id,
                analysis_run_id,
                now,
                result.status,
            ),
        )
        conn.execute(
            "DELETE FROM event_factor_tags WHERE session_id = ? AND factor_id = ?",
            (result_session_id, result.factor_id),
        )
        for tag in result.tags:
            tag_type = str(tag.get("type") or "")
            tag_value = str(tag.get("value") or "")
            conn.execute(
                """
                INSERT INTO factor_tags (result_run_id, session_id, factor_id, tag_type, tag_value)
                VALUES (?, ?, ?, ?, ?)
                """,
                (result.run_id, result_session_id, result.factor_id, tag_type, tag_value),
            )
        for evidence in result.evidence_refs:
            event_id = str(evidence.get("ref_id") or evidence.get("event_id") or "")
            if not event_id:
                continue
            kind = str(evidence.get("kind") or evidence.get("source") or "")
            conn.execute(
                """
                INSERT INTO factor_evidence (result_run_id, session_id, factor_id, event_id, kind, evidence_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (result.run_id, result_session_id, result.factor_id, event_id, kind, _json(evidence)),
            )
        self._insert_event_factor_tags(conn, analysis_run_id, result_session_id, result, now)
        self._insert_datasets(conn, result_session_id, result)
        self._insert_presentations(conn, result_session_id, result)

    def _delete_previous_latest_result(self, conn: sqlite3.Connection, result: FactorResult) -> None:
        row = conn.execute(
            """
            SELECT result_run_id
            FROM factor_result_latest
            WHERE target_type = ?
              AND target_id = ?
              AND factor_id = ?
            """,
            (result.target_type, result.target_id, result.factor_id),
        ).fetchone()
        if row is None:
            return
        previous_result_run_id = str(row["result_run_id"])
        if previous_result_run_id == result.run_id:
            return
        conn.execute("DELETE FROM factor_result_latest WHERE result_run_id = ?", (previous_result_run_id,))
        conn.execute("DELETE FROM factor_results WHERE result_run_id = ?", (previous_result_run_id,))

    def _insert_datasets(self, conn: sqlite3.Connection, session_id: str, result: FactorResult) -> None:
        for dataset in result.datasets:
            records = dataset.get("records")
            record_count = len(records) if isinstance(records, list) else 0
            conn.execute(
                """
                INSERT INTO factor_datasets (
                    result_run_id, session_id, factor_id, dataset_id, semantic_type,
                    shape, primary_key, schema_json, records_json, evidence_policy_json, record_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.run_id,
                    session_id,
                    result.factor_id,
                    str(dataset.get("id") or ""),
                    str(dataset.get("semantic_type") or ""),
                    str(dataset.get("shape") or ""),
                    str(dataset.get("primary_key") or ""),
                    _json(dataset.get("schema") or {}),
                    _json(records if isinstance(records, list) else []),
                    _json(dataset.get("evidence_policy") or {}),
                    record_count,
                ),
            )

    def _insert_presentations(self, conn: sqlite3.Connection, session_id: str, result: FactorResult) -> None:
        for presentation in result.presentations:
            conn.execute(
                """
                INSERT INTO factor_presentations (
                    result_run_id, session_id, factor_id, presentation_id, title,
                    component_ref, data_ref, bindings_json, props_json,
                    routes_json, fallback_json, priority
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.run_id,
                    session_id,
                    result.factor_id,
                    str(presentation.get("id") or ""),
                    str(presentation.get("title") or ""),
                    str(presentation.get("component_ref") or ""),
                    str(presentation.get("data_ref") or ""),
                    _json(presentation.get("bindings") or {}),
                    _json(presentation.get("props") or {}),
                    _json(presentation.get("routes") or []),
                    _json(presentation.get("fallback") or []),
                    _int(presentation.get("priority"), default=100),
                ),
            )

    def _insert_event_factor_tags(
        self,
        conn: sqlite3.Connection,
        analysis_run_id: str,
        session_id: str,
        result: FactorResult,
        now: str,
    ) -> None:
        tags_by_event = _event_tags_from_result(result)
        for event_id, tags in tags_by_event.items():
            if not self._event_exists(conn, session_id, event_id):
                continue
            for tag_type, tag_value in sorted(tags):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO event_factor_tags (
                        session_id, event_id, result_run_id, analysis_run_id, factor_id,
                        tag_type, tag_value, last_run_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        event_id,
                        result.run_id,
                        analysis_run_id,
                        result.factor_id,
                        tag_type,
                        tag_value,
                        now,
                    ),
                )

    def _delete_orphan_analysis_runs(self, conn: sqlite3.Connection, session_id: str) -> None:
        conn.execute(
            """
            DELETE FROM analysis_runs
            WHERE session_id = ?
              AND NOT EXISTS (
                SELECT 1 FROM factor_results
                WHERE factor_results.analysis_run_id = analysis_runs.analysis_run_id
              )
              AND NOT EXISTS (
                SELECT 1 FROM factor_run_errors
                WHERE factor_run_errors.analysis_run_id = analysis_runs.analysis_run_id
              )
            """,
            (session_id,),
        )

    def _insert_error(
        self,
        conn: sqlite3.Connection,
        analysis_run_id: str,
        session_id: str,
        error: Any,
        now: str,
    ) -> None:
        factor_id = _value(error, "factor_id")
        error_type = _value(error, "error_type")
        message = _value(error, "message")
        conn.execute(
            """
            INSERT INTO factor_run_errors (analysis_run_id, session_id, factor_id, error_type, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (analysis_run_id, session_id, factor_id, error_type, message, now),
        )
        conn.execute(
            """
            INSERT INTO factor_run_index (
                session_id, factor_id, source_fingerprint, last_run_at, last_analysis_run_id, last_status
            )
            VALUES (?, ?, '', ?, ?, 'error')
            ON CONFLICT(session_id, factor_id) DO UPDATE SET
                source_fingerprint = excluded.source_fingerprint,
                last_run_at = excluded.last_run_at,
                last_analysis_run_id = excluded.last_analysis_run_id,
                last_status = excluded.last_status
            """,
            (session_id, factor_id, now, analysis_run_id),
        )

    def _event_exists(self, conn: sqlite3.Connection, session_id: str, event_id: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM session_events WHERE session_id = ? AND event_id = ?",
            (session_id, event_id),
        ).fetchone()
        return row is not None

    def _select_factor_run_index(
        self,
        conn: sqlite3.Connection,
        factor_ids: list[str],
    ) -> list[sqlite3.Row]:
        if not factor_ids:
            return list(
                conn.execute(
                    "SELECT session_id, factor_id, source_fingerprint, last_run_at FROM factor_run_index"
                ).fetchall()
            )
        placeholders = ", ".join("?" for _ in factor_ids)
        return list(
            conn.execute(
                f"""
                SELECT session_id, factor_id, source_fingerprint, last_run_at
                FROM factor_run_index
                WHERE factor_id IN ({placeholders})
                """,
                factor_ids,
            ).fetchall()
        )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _json_array(value: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _project_key(metadata: dict[str, Any]) -> str:
    return str(metadata.get("project_key") or metadata.get("session_group_key") or metadata.get("session_cwd") or "")


def _project_label(metadata: dict[str, Any]) -> str:
    explicit = str(metadata.get("project_label") or metadata.get("session_group_label") or "")
    if explicit:
        return explicit
    project_key = _project_key(metadata).rstrip("/").rstrip("\\")
    if not project_key:
        return ""
    return project_key.replace("\\", "/").split("/")[-1]


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _delete_session_source_aliases(
    conn: sqlite3.Connection,
    *,
    provider: str,
    source_ref: str,
    keep_session_id: str,
) -> None:
    conn.execute(
        """
        DELETE FROM sessions
        WHERE provider = ?
          AND source_ref = ?
          AND session_id != ?
        """,
        (provider, source_ref, keep_session_id),
    )


DROP_EVENT_METADATA_KEYS = {
    "provider",
    "scanner_id",
    "scanner_version",
    "source_ref",
    "source_fingerprint",
    "event_locator_json",
    "artifact_locator_json",
    "content_hash",
    "content_preview_redacted",
    "tool_result_hash",
    "tool_result_preview_redacted",
    "role",
    "tool_name",
}


def _compact_event_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in metadata.items()
        if str(key) not in DROP_EVENT_METADATA_KEYS and value not in ("", None, {}, [])
    }


MATERIAL_EVENT_CHANNELS = {"user_input", "assistant_result"}
MATERIALIZED_EVIDENCE_FACTOR_IDS = {
    "official.user-input-sentiment",
    "official.repeated-request",
    "official.task-completion",
    "official.tool-failure-frequency",
}


def _should_store_session_event(event: SessionEvent, *, event_ids: set[str] | None = None) -> bool:
    if event_ids is not None and event.event_id in event_ids:
        return True
    return str(event.metadata.get("factor_channel") or "") in MATERIAL_EVENT_CHANNELS


def _result_evidence_event_ids(results: Iterable[FactorResult]) -> set[str]:
    event_ids: set[str] = set()
    for result in results:
        if not _should_materialize_result_evidence(result.factor_id):
            continue
        for evidence in result.evidence_refs:
            event_id = str(evidence.get("ref_id") or evidence.get("event_id") or "")
            if event_id:
                event_ids.add(event_id)
        for dataset in result.datasets:
            records = dataset.get("records")
            if not isinstance(records, list):
                continue
            for record in records:
                if isinstance(record, dict):
                    _collect_record_event_ids(record, event_ids)
    return event_ids


def _should_materialize_result_evidence(factor_id: str) -> bool:
    return factor_id in MATERIALIZED_EVIDENCE_FACTOR_IDS or factor_id.startswith("default.")


def _collect_record_event_ids(record: dict[str, Any], event_ids: set[str]) -> None:
    for key in ("event_id", "evidence_event_id"):
        event_id = str(record.get(key) or "")
        if event_id:
            event_ids.add(event_id)
    sample_event_ids = record.get("sample_event_ids")
    if not isinstance(sample_event_ids, list):
        return
    for raw_event_id in sample_event_ids:
        event_id = str(raw_event_id or "")
        if event_id:
            event_ids.add(event_id)


MAX_GENERIC_EVENT_TAG_EVIDENCE = 20
MAX_SAMPLE_EVENT_TAGS_PER_RECORD = 10


def _event_tags_from_result(result: FactorResult) -> dict[str, set[tuple[str, str]]]:
    tags_by_event: dict[str, set[tuple[str, str]]] = {}

    for dataset in result.datasets:
        records = dataset.get("records")
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            _add_record_event_tags(tags_by_event, record)
            _add_sample_event_tags(tags_by_event, record, result.tags)

    if len(result.evidence_refs) <= MAX_GENERIC_EVENT_TAG_EVIDENCE:
        for evidence in result.evidence_refs:
            event_id = str(evidence.get("ref_id") or evidence.get("event_id") or "")
            if not event_id:
                continue
            for tag in result.tags:
                _add_event_tag(tags_by_event, event_id, str(tag.get("type") or ""), str(tag.get("value") or ""))

    return tags_by_event


def _add_record_event_tags(tags_by_event: dict[str, set[tuple[str, str]]], record: dict[str, Any]) -> None:
    event_id = str(record.get("event_id") or "")
    if event_id:
        if record.get("sentiment"):
            _add_event_tag(tags_by_event, event_id, "user_sentiment", str(record["sentiment"]))
        if record.get("signal"):
            _add_event_tag(tags_by_event, event_id, "signal", str(record["signal"]))

    evidence_event_id = str(record.get("evidence_event_id") or "")
    if evidence_event_id and record.get("verdict"):
        _add_event_tag(tags_by_event, evidence_event_id, "task_completion", str(record["verdict"]))


def _add_sample_event_tags(
    tags_by_event: dict[str, set[tuple[str, str]]],
    record: dict[str, Any],
    result_tags: list[dict[str, str]],
) -> None:
    sample_event_ids = record.get("sample_event_ids")
    if not isinstance(sample_event_ids, list):
        return
    for raw_event_id in sample_event_ids[:MAX_SAMPLE_EVENT_TAGS_PER_RECORD]:
        event_id = str(raw_event_id)
        if not event_id:
            continue
        for tag in result_tags:
            _add_event_tag(tags_by_event, event_id, str(tag.get("type") or ""), str(tag.get("value") or ""))


def _add_event_tag(tags_by_event: dict[str, set[tuple[str, str]]], event_id: str, tag_type: str, tag_value: str) -> None:
    tag_type = tag_type.strip()
    tag_value = tag_value.strip()
    if not event_id or not tag_type or not tag_value:
        return
    tags_by_event.setdefault(event_id, set()).add((tag_type[:80], tag_value[:80]))


def _value(value: Any, key: str) -> str:
    if isinstance(value, dict):
        return str(value.get(key) or "")
    return str(getattr(value, key, "") or "")


def _int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _content_preview(row: sqlite3.Row | None) -> str:
    if row is None:
        return ""
    return str(row["content_preview_redacted"])


def _event_factor_channel(row: sqlite3.Row) -> str:
    try:
        metadata = _json_dict(str(row["metadata_json"] or "{}"))
    except (IndexError, KeyError):
        return ""
    return str(metadata.get("factor_channel") or "")


def _source_locator(row: sqlite3.Row | None) -> tuple[str, int]:
    if row is None:
        return "", 0
    fallback_ref = str(row["source_ref"])
    try:
        locator = json.loads(str(row["event_locator_json"] or "{}"))
    except json.JSONDecodeError:
        return fallback_ref, 0
    payload = locator.get("payload") if isinstance(locator, dict) else {}
    if not isinstance(payload, dict):
        return fallback_ref, 0
    source_ref = str(payload.get("source_path") or fallback_ref)
    return source_ref, _int(payload.get("line_start"), default=0)


def _dashboard_route_key(factor_id: str) -> str:
    return f"{factor_id}.dashboard"


def _dashboard_component(factor_id: str) -> str:
    components = {
        "default.negative_feedback": "feedback_signal_dashboard",
        "default.open_loop": "open_loop_dashboard",
        "default.repeated_user_requests": "skill_mining_dashboard",
        "default.same_target_rework": "rework_dashboard",
        "default.success_closure_quality": "closure_quality_dashboard",
        "default.task_span_extraction": "task_flow_dashboard",
        "default.tool_failure": "tool_failure_dashboard",
        "default.user_correction_loop": "correction_loop_dashboard",
    }
    return components.get(factor_id, "generic_factor_dashboard")


def _dashboard_priority(factor_id: str) -> int:
    priorities = {
        "default.task_span_extraction": 10,
        "default.tool_failure": 20,
        "default.open_loop": 30,
        "default.user_correction_loop": 40,
        "default.negative_feedback": 50,
        "default.same_target_rework": 60,
        "default.repeated_user_requests": 70,
        "default.success_closure_quality": 80,
    }
    return priorities.get(factor_id, 100)


def _content_hash(content: str) -> str:
    import hashlib

    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _preview(content: str, *, limit: int = 160) -> str:
    return content[:limit]
