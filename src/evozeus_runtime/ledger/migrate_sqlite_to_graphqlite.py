from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from evozeus_runtime.ledger import graph_ids
from evozeus_runtime.ledger.graph_repository import GraphBackend, GraphLedgerRepository
from evozeus_runtime.ledger.legacy_sqlite import LegacySqliteLedger, json_array, json_dict
from evozeus_runtime.ledger.paths import RuntimePaths


@dataclass(frozen=True)
class MigrationCountCheck:
    name: str
    legacy_count: int
    graph_count: int
    operator: str

    @property
    def ok(self) -> bool:
        if self.operator == "==":
            return self.legacy_count == self.graph_count
        if self.operator == "<=":
            return self.legacy_count <= self.graph_count
        if self.operator == ">=":
            return self.legacy_count >= self.graph_count
        raise ValueError(f"unsupported operator: {self.operator}")


@dataclass(frozen=True)
class MigrationResult:
    migration_id: str
    legacy_db_path: Path
    output_db_path: Path
    backup_db_path: Path | None
    checks: list[MigrationCountCheck]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)


def migrate_workspace_sqlite_to_graphqlite(
    *,
    workspace_root: Path,
    legacy_db_path: Path | None = None,
    output_db_path: Path | None = None,
    backup: bool = True,
    backend: GraphBackend = "graphqlite",
) -> MigrationResult:
    paths = RuntimePaths.for_workspace(workspace_root).ensure()
    legacy_path = legacy_db_path or paths.result_index_db
    graph_path = output_db_path or paths.runtime_index_dir / "results.graph.sqlite3"
    backup_path = _backup_legacy_db(legacy_path) if backup else None
    return migrate_sqlite_to_graphqlite(
        legacy_db_path=legacy_path,
        output_db_path=graph_path,
        workspace_root=workspace_root,
        backup_db_path=backup_path,
        backend=backend,
    )


def migrate_sqlite_to_graphqlite(
    *,
    legacy_db_path: Path,
    output_db_path: Path,
    workspace_root: Path,
    backup_db_path: Path | None = None,
    backend: GraphBackend = "graphqlite",
) -> MigrationResult:
    legacy = LegacySqliteLedger(legacy_db_path)
    if output_db_path.exists() and output_db_path.resolve() != legacy_db_path.resolve():
        output_db_path.unlink()
    graph = GraphLedgerRepository(output_db_path, backend=backend, bulk_insert_mode=True)
    migration_id = f"mig_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    migrated_at = _utc_now()
    context = _MigrationContext(
        legacy=legacy,
        graph=graph,
        workspace_root=workspace_root,
        migration_id=migration_id,
        migrated_at=migrated_at,
    )
    context.run()
    checks = _validate_counts(legacy, graph)
    return MigrationResult(
        migration_id=migration_id,
        legacy_db_path=legacy_db_path,
        output_db_path=output_db_path,
        backup_db_path=backup_db_path,
        checks=checks,
    )


class _MigrationContext:
    def __init__(
        self,
        *,
        legacy: LegacySqliteLedger,
        graph: GraphLedgerRepository,
        workspace_root: Path,
        migration_id: str,
        migrated_at: str,
    ):
        self.legacy = legacy
        self.graph = graph
        self.workspace_root = workspace_root
        self.migration_id = migration_id
        self.migrated_at = migrated_at
        self.workspace_node_id = self._workspace_node_id()
        self.sessions = self.legacy.session_by_id()
        self.events = self.legacy.event_by_key()
        self.factor_nodes: dict[str, str] = {}

    def run(self) -> None:
        self._migrate_ledger_meta_and_workspace()
        self._migrate_providers_scanners_factors_routes()
        self._migrate_sources_projects_sessions()
        self._migrate_analysis_runs_results_errors()
        self._migrate_required_events()
        self._migrate_evidence()
        self._migrate_tags()
        self._migrate_datasets_presentations()
        self._migrate_latest_state_and_capabilities()

    def _migrate_ledger_meta_and_workspace(self) -> None:
        self.graph.upsert_node(
            self.workspace_node_id,
            ["Workspace"],
            {
                "workspace_id": self.workspace_node_id.replace("workspace:", "", 1),
                "root_path": str(self.workspace_root),
                "created_at": self.migrated_at,
                "schema_version": "graphqlite_sparse_evidence.v0",
                "privacy_upload_default": False,
            },
        )
        meta_id = f"ledger_meta:{self.migration_id}"
        self.graph.upsert_node(
            meta_id,
            ["LedgerMeta"],
            {
                "migration_id": self.migration_id,
                "legacy_schema_version": self.legacy.schema_version(),
                "migrated_at": self.migrated_at,
                "legacy_db_path": str(self.legacy.db_path),
            },
        )
        self.graph.upsert_edge(self.workspace_node_id, meta_id, "HAS_LEDGER_META", {"migrated_at": self.migrated_at})

    def _migrate_providers_scanners_factors_routes(self) -> None:
        for provider in self._providers():
            provider_node_id = graph_ids.provider_id(provider)
            self.graph.upsert_node(provider_node_id, ["Provider"], {"provider": provider, "display_name": provider})
            self.graph.upsert_edge(self.workspace_node_id, provider_node_id, "HAS_PROVIDER", {})

        for scanner_key in self._scanners():
            scanner_node_id = graph_ids.scanner_id(scanner_key[0], scanner_key[1])
            self.graph.upsert_node(
                scanner_node_id,
                ["Scanner"],
                {"scanner_id": scanner_key[0], "scanner_version": scanner_key[1]},
            )

        installed_versions: set[tuple[str, str]] = set()
        for row in self.legacy.rows("installed_factors"):
            factor_id_value = str(row.get("factor_id") or "")
            version = str(row.get("version") or "")
            if not factor_id_value:
                continue
            installed_versions.add((factor_id_value, version))
            node_id = self._ensure_factor_node(factor_id_value, version)
            self.graph.upsert_node(
                node_id,
                ["Factor"],
                {
                    "factor_id": factor_id_value,
                    "version": version,
                    "source": str(row.get("source") or ""),
                    "enabled": bool(row.get("enabled")),
                    "runtime_mode": str(row.get("runtime_mode") or ""),
                    "status": str(row.get("status") or ""),
                    "manifest_path": str(row.get("manifest_path") or ""),
                    "factor_xml_path": str(row.get("factor_xml_path") or ""),
                },
            )

        for row in self.legacy.rows("factor_results"):
            factor_id_value = str(row.get("factor_id") or "")
            version = str(row.get("factor_version") or "")
            if factor_id_value and (factor_id_value, version) not in installed_versions:
                self._ensure_factor_node(factor_id_value, version, stub=True)

        for row in self.legacy.rows("factor_result_routes"):
            factor_id_value = str(row.get("factor_id") or "")
            route_area = str(row.get("route_area") or "")
            route_key = str(row.get("route_key") or "")
            if not route_area or not route_key:
                continue
            route_node_id = graph_ids.route_id(route_area, route_key)
            self.graph.upsert_node(
                route_node_id,
                ["Route"],
                {
                    "route_area": route_area,
                    "route_key": route_key,
                    "component": str(row.get("component") or ""),
                    "title": str(row.get("title") or ""),
                    "priority": _int(row.get("priority"), default=100),
                    "enabled": bool(row.get("enabled")),
                    "result_type": str(row.get("result_type") or ""),
                },
            )
            if factor_id_value:
                self.graph.upsert_edge(self._ensure_factor_node(factor_id_value), route_node_id, "ROUTES_TO", {})

    def _migrate_sources_projects_sessions(self) -> None:
        for row in self.legacy.rows("source_refs"):
            provider = str(row.get("provider") or "")
            source_ref = str(row.get("source_ref") or "")
            if not provider or not source_ref:
                continue
            source_node_id = graph_ids.source_ref_id(provider, source_ref)
            self.graph.upsert_node(
                source_node_id,
                ["SourceRef"],
                {
                    "provider": provider,
                    "source_ref": source_ref,
                    "source_size": _int(row.get("source_size"), default=0),
                    "source_mtime": str(row.get("source_mtime") or ""),
                    "source_fingerprint": str(row.get("source_fingerprint") or ""),
                    "last_seen_at": str(row.get("last_seen_at") or ""),
                    "source_kind": "local_file",
                    "exists_at_migration": Path(source_ref).exists(),
                },
            )
            self.graph.upsert_edge(graph_ids.provider_id(provider), source_node_id, "DISCOVERED", {})

        indexed_counts = _counts_by(self.legacy.rows("session_events"), "session_id")
        for row in self.legacy.rows("sessions"):
            provider = str(row.get("provider") or "")
            session_id_value = str(row.get("session_id") or "")
            source_ref = str(row.get("source_ref") or "")
            if not provider or not session_id_value:
                continue
            metadata = json_dict(str(row.get("metadata_json") or "{}"))
            project_key = str(row.get("project_key") or metadata.get("session_group_key") or "")
            project_label = str(row.get("project_label") or metadata.get("session_group_label") or project_key.rsplit("/", 1)[-1])
            project_node_id = graph_ids.project_id(provider, project_key)
            session_node_id = graph_ids.session_id(provider, session_id_value)
            source_node_id = graph_ids.source_ref_id(provider, source_ref)
            self.graph.upsert_node(
                project_node_id,
                ["Project"],
                {"provider": provider, "project_key": project_key, "project_label": project_label},
            )
            self.graph.upsert_node(
                session_node_id,
                ["Session"],
                {
                    "session_id": session_id_value,
                    "provider": provider,
                    "title": str(metadata.get("session_title") or ""),
                    "cwd": str(metadata.get("session_cwd") or ""),
                    "project_key": project_key,
                    "project_label": project_label,
                    "source_ref": source_ref,
                    "event_count": _int(row.get("event_count"), default=0),
                    "indexed_event_count": indexed_counts.get(session_id_value, 0),
                    "evidence_event_count": 0,
                    "discovered_at": str(row.get("discovered_at") or ""),
                    "first_seen_at": str(row.get("first_seen_at") or ""),
                    "last_seen_at": str(row.get("last_seen_at") or ""),
                    "loaded_at": str(row.get("loaded_at") or ""),
                    "updated_at": str(metadata.get("session_updated_at") or ""),
                    "first_user_preview": "",
                    "last_assistant_preview": "",
                    "candidate_label": str(metadata.get("candidate_label") or ""),
                },
            )
            self.graph.upsert_edge(graph_ids.provider_id(provider), project_node_id, "HAS_PROJECT", {})
            self.graph.upsert_edge(project_node_id, session_node_id, "HAS_SESSION", {})
            self.graph.upsert_edge(source_node_id, session_node_id, "MATERIALIZED_AS", {})

    def _migrate_analysis_runs_results_errors(self) -> None:
        for row in self.legacy.rows("analysis_runs"):
            analysis_run_id_value = str(row.get("analysis_run_id") or "")
            session_id_value = str(row.get("session_id") or "")
            provider = str(row.get("provider") or self._session_provider(session_id_value))
            if not analysis_run_id_value:
                continue
            node_id = graph_ids.analysis_run_id(analysis_run_id_value)
            self.graph.upsert_node(
                node_id,
                ["AnalysisRun"],
                {
                    "analysis_run_id": analysis_run_id_value,
                    "provider": provider,
                    "started_at": str(row.get("started_at") or ""),
                    "completed_at": str(row.get("completed_at") or ""),
                    "factor_ids_json": str(row.get("factor_ids_json") or "[]"),
                    "result_count": _int(row.get("result_count"), default=0),
                    "error_count": _int(row.get("error_count"), default=0),
                    "status": str(row.get("status") or ""),
                },
            )
            if session_id_value:
                self.graph.upsert_edge(node_id, graph_ids.session_id(provider, session_id_value), "ANALYZED", {})
            for factor_id_value in json_array(str(row.get("factor_ids_json") or "[]")):
                if factor_id_value:
                    self.graph.upsert_edge(
                        self._ensure_factor_node(str(factor_id_value)),
                        node_id,
                        "RAN_IN",
                        {},
                    )

        for row in self.legacy.rows("factor_results"):
            result_run_id = str(row.get("result_run_id") or "")
            analysis_run_id_value = str(row.get("analysis_run_id") or "")
            session_id_value = str(row.get("session_id") or "")
            provider = self._session_provider(session_id_value)
            if not result_run_id:
                continue
            node_id = graph_ids.factor_result_id(result_run_id)
            factor_id_value = str(row.get("factor_id") or "")
            factor_version = str(row.get("factor_version") or "")
            self.graph.upsert_node(
                node_id,
                ["FactorResult"],
                {
                    "result_run_id": result_run_id,
                    "factor_id": factor_id_value,
                    "factor_version": factor_version,
                    "framework_id": str(row.get("framework_id") or ""),
                    "stage": str(row.get("stage") or ""),
                    "target_type": str(row.get("target_type") or ""),
                    "target_id": str(row.get("target_id") or ""),
                    "status": str(row.get("status") or ""),
                    "confidence": _float(row.get("confidence"), default=0.0),
                    "verdict_signals_json": str(row.get("verdict_signals_json") or "[]"),
                    "scores_json": str(row.get("scores_json") or "{}"),
                    "statistics_json": str(row.get("statistics_json") or "{}"),
                    "notes_json": str(row.get("notes_json") or "[]"),
                    "created_at": str(row.get("created_at") or ""),
                },
            )
            if analysis_run_id_value:
                self.graph.upsert_edge(graph_ids.analysis_run_id(analysis_run_id_value), node_id, "PRODUCED", {})
            if factor_id_value:
                self.graph.upsert_edge(self._ensure_factor_node(factor_id_value, factor_version), graph_ids.analysis_run_id(analysis_run_id_value), "RAN_IN", {})
            target_node_id = self._target_node_id(provider, str(row.get("target_type") or ""), str(row.get("target_id") or ""), session_id_value)
            self.graph.upsert_edge(node_id, target_node_id, "ABOUT", {})

        for ordinal, row in enumerate(self.legacy.rows("factor_run_errors"), start=1):
            analysis_run_id_value = str(row.get("analysis_run_id") or "")
            factor_id_value = str(row.get("factor_id") or "")
            node_id = graph_ids.run_error_id(analysis_run_id_value, factor_id_value, ordinal)
            self.graph.upsert_node(
                node_id,
                ["RunError"],
                {
                    "analysis_run_id": analysis_run_id_value,
                    "factor_id": factor_id_value,
                    "error_type": str(row.get("error_type") or ""),
                    "message": str(row.get("message") or ""),
                    "created_at": str(row.get("created_at") or ""),
                },
            )
            self.graph.upsert_edge(graph_ids.analysis_run_id(analysis_run_id_value), node_id, "FAILED_WITH", {})
            if factor_id_value:
                self.graph.upsert_edge(node_id, self._ensure_factor_node(factor_id_value), "ABOUT_FACTOR", {})

    def _migrate_required_events(self) -> None:
        for session_id_value, event_id in sorted(self.legacy.required_event_keys()):
            self._ensure_event_node(session_id_value, event_id, reason="migration_required")

    def _migrate_evidence(self) -> None:
        for row in self.legacy.rows("factor_evidence"):
            result_run_id = str(row.get("result_run_id") or "")
            session_id_value = str(row.get("session_id") or "")
            event_id = str(row.get("event_id") or "")
            if not result_run_id or not session_id_value or not event_id:
                continue
            event_node_id = self._ensure_event_node(session_id_value, event_id, reason="evidence")
            self.graph.upsert_edge(
                graph_ids.factor_result_id(result_run_id),
                event_node_id,
                "USES_EVIDENCE",
                {
                    "kind": str(row.get("kind") or ""),
                },
            )

    def _migrate_tags(self) -> None:
        rollups: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in self.legacy.rows("factor_tags"):
            session_id_value = str(row.get("session_id") or "")
            result_run_id = str(row.get("result_run_id") or "")
            tag_type = str(row.get("tag_type") or "")
            tag_value = str(row.get("tag_value") or "")
            if not session_id_value or not tag_type or not tag_value:
                continue
            provider = self._session_provider(session_id_value)
            target_node_id = graph_ids.session_id(provider, session_id_value)
            self._create_tag_assertion(
                result_run_id=result_run_id,
                target_node_id=target_node_id,
                target_type="session",
                tag_type=tag_type,
                tag_value=tag_value,
                source_factor_id=str(row.get("factor_id") or ""),
            )
            _add_rollup(rollups, session_id_value, tag_type, tag_value, evidence=False)

        for row in self.legacy.rows("event_factor_tags"):
            session_id_value = str(row.get("session_id") or "")
            event_id = str(row.get("event_id") or "")
            result_run_id = str(row.get("result_run_id") or "")
            tag_type = str(row.get("tag_type") or "")
            tag_value = str(row.get("tag_value") or "")
            if not session_id_value or not event_id or not tag_type or not tag_value:
                continue
            event_node_id = self._ensure_event_node(session_id_value, event_id, reason="tagged")
            assertion_node_id = self._create_tag_assertion(
                result_run_id=result_run_id,
                target_node_id=event_node_id,
                target_type="chat_event",
                tag_type=tag_type,
                tag_value=tag_value,
                source_factor_id=str(row.get("factor_id") or ""),
                analysis_run_id=str(row.get("analysis_run_id") or ""),
            )
            tag_node_id = graph_ids.tag_id(tag_type, tag_value)
            self.graph.upsert_edge(event_node_id, tag_node_id, "TAGGED_AS", {})
            self.graph.upsert_edge(graph_ids.factor_result_id(result_run_id), assertion_node_id, "EMITTED", {})
            _add_rollup(rollups, session_id_value, tag_type, tag_value, evidence=True, latest_at=str(row.get("last_run_at") or ""))

        for (session_id_value, tag_type, tag_value), payload in rollups.items():
            provider = self._session_provider(session_id_value)
            self.graph.upsert_edge(
                graph_ids.session_id(provider, session_id_value),
                graph_ids.tag_id(tag_type, tag_value),
                "HAS_TAG_ROLLUP",
                payload,
            )

    def _migrate_datasets_presentations(self) -> None:
        for row in self.legacy.rows("factor_datasets"):
            result_run_id = str(row.get("result_run_id") or "")
            dataset_id_value = str(row.get("dataset_id") or "")
            if not result_run_id or not dataset_id_value:
                continue
            dataset_node_id = graph_ids.dataset_id(result_run_id, dataset_id_value)
            records = json_array(str(row.get("records_json") or "[]"))
            self.graph.upsert_node(
                dataset_node_id,
                ["Dataset"],
                {
                    "dataset_id": dataset_id_value,
                    "semantic_type": str(row.get("semantic_type") or ""),
                    "shape": str(row.get("shape") or ""),
                    "primary_key": str(row.get("primary_key") or ""),
                    "schema_json": str(row.get("schema_json") or "{}"),
                    "record_count": _int(row.get("record_count"), default=len(records)),
                    "evidence_policy_json": str(row.get("evidence_policy_json") or "{}"),
                    "records_json": str(row.get("records_json") or "[]"),
                },
            )
            self.graph.upsert_edge(graph_ids.factor_result_id(result_run_id), dataset_node_id, "HAS_DATASET", {})
            for index, record in enumerate(records, start=1):
                if not isinstance(record, dict):
                    continue
                record_event_ids = _record_event_ids(record)
                if not record_event_ids:
                    continue
                record_id = str(record.get(str(row.get("primary_key") or "")) or record.get("id") or index)
                record_node_id = graph_ids.dataset_record_id(result_run_id, dataset_id_value, record_id)
                self.graph.upsert_node(record_node_id, ["DatasetRecord"], {"record_id": record_id, "record_json": record})
                self.graph.upsert_edge(dataset_node_id, record_node_id, "HAS_RECORD", {})
                for event_id in record_event_ids:
                    event_node_id = self._ensure_event_node(str(row.get("session_id") or ""), event_id, reason="dataset_record")
                    self.graph.upsert_edge(record_node_id, event_node_id, "EVIDENCES", {})

        for row in self.legacy.rows("factor_presentations"):
            result_run_id = str(row.get("result_run_id") or "")
            presentation_id_value = str(row.get("presentation_id") or "")
            if not result_run_id or not presentation_id_value:
                continue
            presentation_node_id = graph_ids.presentation_id(result_run_id, presentation_id_value)
            self.graph.upsert_node(
                presentation_node_id,
                ["Presentation"],
                {
                    "presentation_id": presentation_id_value,
                    "title": str(row.get("title") or ""),
                    "component_ref": str(row.get("component_ref") or ""),
                    "data_ref": str(row.get("data_ref") or ""),
                    "bindings_json": str(row.get("bindings_json") or "{}"),
                    "props_json": str(row.get("props_json") or "{}"),
                    "fallback_json": str(row.get("fallback_json") or "[]"),
                    "priority": _int(row.get("priority"), default=100),
                },
            )
            self.graph.upsert_edge(graph_ids.factor_result_id(result_run_id), presentation_node_id, "HAS_PRESENTATION", {})
            for route_key in json_array(str(row.get("routes_json") or "[]")):
                route_node_id = graph_ids.route_id("presentation", str(route_key))
                self.graph.upsert_node(route_node_id, ["Route"], {"route_area": "presentation", "route_key": str(route_key)})
                self.graph.upsert_edge(presentation_node_id, route_node_id, "ROUTES_TO", {})

    def _migrate_latest_state_and_capabilities(self) -> None:
        for row in self.legacy.rows("factor_run_index"):
            session_id_value = str(row.get("session_id") or "")
            factor_id_value = str(row.get("factor_id") or "")
            provider = self._session_provider(session_id_value)
            if session_id_value and factor_id_value:
                self.graph.upsert_edge(
                    graph_ids.session_id(provider, session_id_value),
                    self._ensure_factor_node(factor_id_value, str(row.get("factor_version") or "")),
                    "HAS_FACTOR_STATE",
                    {
                        "last_run_at": str(row.get("last_run_at") or ""),
                        "last_analysis_run_id": str(row.get("last_analysis_run_id") or ""),
                        "last_result_run_id": str(row.get("last_result_run_id") or ""),
                        "last_status": str(row.get("last_status") or ""),
                        "stale_reason": str(row.get("stale_reason") or ""),
                    },
                )

        for row in self.legacy.rows("factor_result_latest"):
            result_run_id = str(row.get("result_run_id") or "")
            target_type = str(row.get("target_type") or "")
            target_id = str(row.get("target_id") or "")
            factor_id_value = str(row.get("factor_id") or "")
            target_node_id = self._target_node_id("", target_type, target_id, target_id)
            self.graph.upsert_edge(
                target_node_id,
                graph_ids.factor_result_id(result_run_id),
                "LATEST_FACTOR_RESULT",
                {
                    "factor_id": factor_id_value,
                    "analysis_run_id": str(row.get("analysis_run_id") or ""),
                    "last_run_at": str(row.get("last_run_at") or ""),
                    "status": str(row.get("status") or ""),
                },
            )

        for row in self.legacy.rows("factor_capabilities"):
            factor_id_value = str(row.get("factor_id") or "")
            version = str(row.get("version") or "")
            provider = str(row.get("provider") or "")
            target_type = str(row.get("target_type") or "")
            factor_node_id = self._ensure_factor_node(factor_id_value, version)
            if provider:
                self.graph.upsert_edge(
                    factor_node_id,
                    graph_ids.provider_id(provider),
                    "SUPPORTS",
                    {"supported": bool(row.get("supported")), "reason": str(row.get("reason") or "")},
                )
            if target_type:
                target_type_node_id = graph_ids.target_type_id(target_type)
                self.graph.upsert_node(target_type_node_id, ["TargetType"], {"target_type": target_type})
                self.graph.upsert_edge(factor_node_id, target_type_node_id, "SUPPORTS_TARGET", {"supported": bool(row.get("supported"))})

    def _create_tag_assertion(
        self,
        *,
        result_run_id: str,
        target_node_id: str,
        target_type: str,
        tag_type: str,
        tag_value: str,
        source_factor_id: str,
        analysis_run_id: str = "",
    ) -> str:
        tag_node_id = graph_ids.tag_id(tag_type, tag_value)
        assertion_node_id = graph_ids.tag_assertion_id(result_run_id, target_node_id, tag_type, tag_value)
        self.graph.upsert_node(
            tag_node_id,
            ["Tag"],
            {
                "type": tag_type,
                "value": tag_value,
                "display_label": tag_value,
                "namespace": "",
            },
        )
        self.graph.upsert_node(
            assertion_node_id,
            ["TagAssertion"],
            {
                "assertion_id": assertion_node_id,
                "tag_type": tag_type,
                "tag_value": tag_value,
                "target_node_id": target_node_id,
                "target_type": target_type,
                "source_kind": "migration",
                "source_factor_id": source_factor_id,
                "source_result_run_id": result_run_id,
                "analysis_run_id": analysis_run_id,
                "confidence": 0.0,
                "status": "active",
                "created_at": self.migrated_at,
                "updated_at": self.migrated_at,
                "reason": "legacy_sqlite_migration",
            },
        )
        self.graph.upsert_edge(assertion_node_id, tag_node_id, "ASSERTS", {})
        self.graph.upsert_edge(assertion_node_id, target_node_id, "ON", {})
        if result_run_id:
            self.graph.upsert_edge(graph_ids.factor_result_id(result_run_id), assertion_node_id, "EMITTED", {})
        return assertion_node_id

    def _ensure_event_node(self, session_id_value: str, event_id: str, *, reason: str) -> str:
        provider = self._session_provider(session_id_value)
        event_row = self.events.get((session_id_value, event_id))
        session_node_id = graph_ids.session_id(provider, session_id_value)
        if event_row is None:
            node_id = graph_ids.event_stub_id(provider, session_id_value, event_id)
            self.graph.upsert_node(
                node_id,
                ["ChatEventRef", "EventStub"],
                {
                    "event_id": event_id,
                    "provider": provider,
                    "stub": True,
                    "stub_reason": "missing_legacy_session_event",
                    "created_from_migration_id": self.migration_id,
                    "completeness": "stub",
                },
            )
            self.graph.upsert_edge(session_node_id, node_id, "HAS_EVIDENCE_EVENT", {"materialization_reason": reason})
            return node_id

        node_id = graph_ids.chat_event_id(provider, session_id_value, event_id)
        content_preview = str(event_row.get("content_preview_redacted") or "")
        tool_preview = str(event_row.get("tool_result_preview_redacted") or "")
        completeness = "legacy_preview_only" if content_preview or tool_preview else "legacy_index_only"
        self.graph.upsert_node(
            node_id,
                ["ChatEventRef"],
                {
                    "event_id": event_id,
                    "event_index": _int(event_row.get("event_index"), default=0),
                    "role": str(event_row.get("role") or ""),
                    "content_kind": _content_kind(event_row),
                    "factor_channel": json_dict(str(event_row.get("metadata_json") or "{}")).get("factor_channel", ""),
                    "record_type": json_dict(str(event_row.get("metadata_json") or "{}")).get("codex_record_type", ""),
                    "payload_type": json_dict(str(event_row.get("metadata_json") or "{}")).get("codex_event_type", ""),
                    "tool_name": str(event_row.get("tool_name") or ""),
                    "source_ref": str(event_row.get("source_ref") or ""),
                    "source_line_start": _source_line(event_row),
                    "content_hash": str(event_row.get("content_hash") or ""),
                    "content_preview_redacted": content_preview,
                    "tool_result_hash": str(event_row.get("tool_result_hash") or ""),
                    "tool_result_preview_redacted": tool_preview,
                    "locator_json": str(event_row.get("event_locator_json") or "{}"),
                    "completeness": completeness,
                },
            )
        self.graph.upsert_edge(
            session_node_id,
            node_id,
            "HAS_EVIDENCE_EVENT",
            {"event_index": _int(event_row.get("event_index"), default=0), "materialization_reason": reason},
        )
        scanner_id_value = str(event_row.get("scanner_id") or "unknown")
        scanner_version = str(event_row.get("scanner_version") or "")
        self.graph.upsert_edge(graph_ids.scanner_id(scanner_id_value, scanner_version), node_id, "INDEXED_EVENT", {})
        return node_id

    def _ensure_factor_node(self, factor_id_value: str, version: str = "", *, stub: bool = False) -> str:
        key = f"{factor_id_value}\0{version}"
        if key in self.factor_nodes:
            return self.factor_nodes[key]
        node_id = graph_ids.factor_id(factor_id_value, version)
        self.factor_nodes[key] = node_id
        self.graph.upsert_node(
            node_id,
            ["Factor"],
            {
                "factor_id": factor_id_value,
                "version": version,
                "stub": stub or not version,
                "stub_reason": "missing_installed_factor" if stub or not version else "",
                "created_from_migration_id": self.migration_id if stub or not version else "",
            },
        )
        return node_id

    def _target_node_id(self, provider: str, target_type: str, target_id: str, fallback_session_id: str) -> str:
        if target_type == "session" and target_id:
            resolved_provider = provider or self._session_provider(target_id) or self._session_provider(fallback_session_id)
            return graph_ids.session_id(resolved_provider, target_id)
        node_id = graph_ids.target_stub_id(target_type, target_id)
        self.graph.upsert_node(
            node_id,
            ["TargetStub"],
            {
                "target_type": target_type,
                "target_id": target_id,
                "stub": True,
                "stub_reason": "legacy_target_not_materialized",
                "created_from_migration_id": self.migration_id,
            },
        )
        return node_id

    def _providers(self) -> set[str]:
        providers = {str(row.get("provider") or "") for row in self.legacy.rows("source_refs")}
        providers.update(str(row.get("provider") or "") for row in self.legacy.rows("sessions"))
        providers.update(str(row.get("provider") or "") for row in self.legacy.rows("analysis_runs"))
        return {provider for provider in providers if provider}

    def _scanners(self) -> set[tuple[str, str]]:
        scanners = {
            (str(row.get("scanner_id") or "unknown"), str(row.get("scanner_version") or ""))
            for row in self.legacy.rows("session_events")
        }
        return scanners or {("unknown", "")}

    def _session_provider(self, session_id_value: str) -> str:
        row = self.sessions.get(session_id_value)
        if row is None:
            return "unknown"
        return str(row.get("provider") or "unknown")

    def _workspace_node_id(self) -> str:
        config_path = self.workspace_root / ".evozeus" / "config.json"
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                config = {}
            workspace_id = str(config.get("workspace_id") or "")
            if workspace_id:
                return f"workspace:{workspace_id}"
        return graph_ids.workspace_id_from_root(str(self.workspace_root.resolve()))


def _validate_counts(legacy: LegacySqliteLedger, graph: GraphLedgerRepository) -> list[MigrationCountCheck]:
    return [
        MigrationCountCheck("sessions", legacy.count("sessions"), graph.count_nodes("Session"), "=="),
        MigrationCountCheck("source_refs", legacy.count("source_refs"), graph.count_nodes("SourceRef"), "=="),
        MigrationCountCheck("factor_results", legacy.count("factor_results"), graph.count_nodes("FactorResult"), "=="),
        MigrationCountCheck("analysis_runs", legacy.count("analysis_runs"), graph.count_nodes("AnalysisRun"), "=="),
        MigrationCountCheck("factor_tags", legacy.count("factor_tags"), graph.count_nodes("TagAssertion"), "<="),
        MigrationCountCheck(
            "event_factor_tags",
            legacy.count("event_factor_tags"),
            graph.count_nodes("TagAssertion", {"target_type": "chat_event"}),
            "==",
        ),
        MigrationCountCheck("factor_evidence", legacy.count("factor_evidence"), graph.count_edges("USES_EVIDENCE"), "=="),
        MigrationCountCheck("factor_run_errors", legacy.count("factor_run_errors"), graph.count_nodes("RunError"), "=="),
        MigrationCountCheck("session_events_sparse", legacy.count("session_events"), graph.count_nodes("ChatEventRef"), ">="),
    ]


def _backup_legacy_db(legacy_path: Path) -> Path:
    backup_path = legacy_path.with_name(f"{legacy_path.name}.legacy")
    if legacy_path.exists():
        shutil.copy2(legacy_path, backup_path)
    return backup_path


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _counts_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _record_event_ids(record: dict[str, Any]) -> list[str]:
    event_ids: list[str] = []
    for key in ("event_id", "evidence_event_id"):
        event_id = str(record.get(key) or "")
        if event_id:
            event_ids.append(event_id)
    sample_event_ids = record.get("sample_event_ids")
    if isinstance(sample_event_ids, list):
        event_ids.extend(str(event_id) for event_id in sample_event_ids if str(event_id or ""))
    return event_ids


def _source_line(event_row: dict[str, Any]) -> int:
    locator = json_dict(str(event_row.get("event_locator_json") or "{}"))
    payload = locator.get("payload") if isinstance(locator, dict) else {}
    if not isinstance(payload, dict):
        return 0
    return _int(payload.get("line_start"), default=0)


def _content_kind(event_row: dict[str, Any]) -> str:
    metadata = json_dict(str(event_row.get("metadata_json") or "{}"))
    factor_channel = str(metadata.get("factor_channel") or "")
    role = str(event_row.get("role") or "")
    if factor_channel == "user_input" or role == "user":
        return "user_message"
    if factor_channel == "assistant_result" or role in {"assistant", "task_complete"}:
        return "assistant_message"
    if role == "tool":
        return "tool_output"
    return "runtime_event"


def _add_rollup(
    rollups: dict[tuple[str, str, str], dict[str, Any]],
    session_id_value: str,
    tag_type: str,
    tag_value: str,
    *,
    evidence: bool,
    latest_at: str = "",
) -> None:
    key = (session_id_value, tag_type, tag_value)
    payload = rollups.setdefault(
        key,
        {
            "count": 0,
            "evidence_count": 0,
            "latest_at": "",
            "confidence_max": 0.0,
        },
    )
    payload["count"] += 1
    if evidence:
        payload["evidence_count"] += 1
    if latest_at and latest_at > str(payload["latest_at"]):
        payload["latest_at"] = latest_at
