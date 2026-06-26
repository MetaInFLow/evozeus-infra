from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal, Protocol


GraphBackend = Literal["graphqlite", "sqlite"]


class GraphQLiteNotInstalledError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(
            "GraphQLite is required for graph ledger writes. Install with "
            "`pip install 'evozeus-runtime[graph]'` or `pip install graphqlite`."
        )


class _GraphBackend(Protocol):
    def upsert_node(self, node_id: str, labels: list[str], props: dict[str, Any]) -> None: ...

    def upsert_nodes(self, nodes: list[tuple[str, list[str], dict[str, Any]]]) -> None: ...

    def upsert_edge(self, source_id: str, target_id: str, rel_type: str, props: dict[str, Any]) -> None: ...

    def upsert_edges(self, edges: list[tuple[str, str, str, dict[str, Any]]]) -> None: ...

    def insert_graph(
        self,
        nodes: list[tuple[str, list[str], dict[str, Any]]],
        edges: list[tuple[str, str, str, dict[str, Any]]],
    ) -> None: ...

    def get_node(self, node_id: str) -> dict[str, Any] | None: ...

    def get_all_nodes(self, label: str | None = None) -> list[dict[str, Any]]: ...

    def get_all_edges(self) -> list[dict[str, Any]]: ...

    def delete_node(self, node_id: str) -> None: ...

    def delete_edge(self, source_id: str, target_id: str, rel_type: str | None = None) -> None: ...

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...

    def count_nodes(self, label: str | None = None, props: dict[str, Any] | None = None) -> int: ...

    def count_edges(self, rel_type: str | None = None) -> int: ...

    def stats(self) -> dict[str, int]: ...


class GraphLedgerRepository:
    def __init__(
        self,
        db_path: Path,
        *,
        backend: GraphBackend = "graphqlite",
        namespace: str = "evozeus",
        batch_size: int = 1000,
        bulk_insert_mode: bool = False,
    ):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.batch_size = max(1, batch_size)
        self._node_buffer: list[tuple[str, list[str], dict[str, Any]]] = []
        self._edge_buffer: list[tuple[str, str, str, dict[str, Any]]] = []
        self.bulk_insert_mode = bulk_insert_mode
        if backend == "graphqlite":
            self._backend: _GraphBackend = _GraphQLiteBackend(db_path, namespace=namespace)
        elif backend == "sqlite":
            self._backend = _SqliteGraphBackend(db_path)
        else:
            raise ValueError(f"unknown graph backend: {backend}")

    @classmethod
    def for_tests(cls, db_path: Path) -> GraphLedgerRepository:
        return cls(db_path, backend="sqlite")

    def upsert_node(self, node_id: str, labels: Iterable[str], props: dict[str, Any] | None = None) -> None:
        clean_labels = _clean_labels(labels)
        clean_props = _clean_props(props or {})
        self._node_buffer.append((node_id, clean_labels, clean_props))
        if not self.bulk_insert_mode and len(self._node_buffer) >= self.batch_size:
            self.flush_nodes()

    def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        props: dict[str, Any] | None = None,
    ) -> None:
        rel_type = rel_type.strip()
        if not rel_type:
            raise ValueError("rel_type must not be empty")
        clean_props = _clean_props(props or {})
        self._edge_buffer.append((source_id, target_id, rel_type, clean_props))
        if not self.bulk_insert_mode and len(self._edge_buffer) >= self.batch_size:
            self.flush_edges()

    def flush(self) -> None:
        if self.bulk_insert_mode:
            self.flush_bulk_insert()
            return
        self.flush_nodes()
        self.flush_edges()

    def flush_bulk_insert(self) -> None:
        if not self._node_buffer and not self._edge_buffer:
            return
        nodes = _dedupe_node_buffer(self._node_buffer)
        edges = _dedupe_edge_buffer(self._edge_buffer)
        self._node_buffer = []
        self._edge_buffer = []
        self._backend.insert_graph(nodes, edges)

    def flush_nodes(self) -> None:
        if not self._node_buffer:
            return
        pending = self._node_buffer
        self._node_buffer = []
        self._backend.upsert_nodes(pending)

    def flush_edges(self) -> None:
        if not self._edge_buffer:
            return
        self.flush_nodes()
        pending = self._edge_buffer
        self._edge_buffer = []
        self._backend.upsert_edges(pending)

    def set_node_property(self, node_id: str, key: str, value: Any, source: str) -> None:
        node = self.get_node(node_id) or {}
        props = {key: value, "property_sources": {**node.get("property_sources", {}), key: source}}
        labels = node.get("labels") or [node.get("_label") or "Entity"]
        self.upsert_node(node_id, labels, props)

    def set_edge_property(self, source_id: str, target_id: str, rel_type: str, key: str, value: Any, source: str) -> None:
        edge = self.get_edge(source_id, target_id, rel_type) or {}
        props = {key: value, "property_sources": {**edge.get("property_sources", {}), key: source}}
        self.upsert_edge(source_id, target_id, rel_type, props)

    def delete_node(self, node_id: str, *, cascade_policy: str = "delete_incident_edges") -> None:
        if cascade_policy != "delete_incident_edges":
            raise ValueError(f"unsupported cascade policy: {cascade_policy}")
        self.flush()
        self._backend.delete_node(node_id)

    def delete_edge(self, source_id: str, target_id: str, rel_type: str | None = None) -> None:
        self.flush()
        self._backend.delete_edge(source_id, target_id, rel_type)

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        self.flush()
        return self._backend.get_node(node_id)

    def get_edge(self, source_id: str, target_id: str, rel_type: str | None = None) -> dict[str, Any] | None:
        for edge in self.get_all_edges(rel_type=rel_type):
            if edge["_src"] == source_id and edge["_dst"] == target_id:
                return edge
        return None

    def get_all_nodes(self, label: str | None = None) -> list[dict[str, Any]]:
        self.flush()
        return self._backend.get_all_nodes(label)

    def get_all_edges(self, rel_type: str | None = None) -> list[dict[str, Any]]:
        self.flush()
        edges = self._backend.get_all_edges()
        if rel_type is None:
            return edges
        return [edge for edge in edges if edge.get("_rel_type") == rel_type or edge.get("rel_type") == rel_type]

    def count_nodes(self, label: str | None = None, props: dict[str, Any] | None = None) -> int:
        self.flush()
        return self._backend.count_nodes(label, props)

    def count_edges(self, rel_type: str | None = None) -> int:
        self.flush()
        return self._backend.count_edges(rel_type)

    def stats(self) -> dict[str, int]:
        self.flush()
        return self._backend.stats()

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self.flush()
        return self._backend.query(cypher, params)


class _GraphQLiteBackend:
    def __init__(self, db_path: Path, *, namespace: str):
        try:
            from graphqlite import Graph
        except ImportError as exc:
            raise GraphQLiteNotInstalledError() from exc

        self.graph = Graph(str(db_path), namespace=namespace)

    def upsert_node(self, node_id: str, labels: list[str], props: dict[str, Any]) -> None:
        self.graph.upsert_node(node_id, props, label=labels[0])

    def upsert_nodes(self, nodes: list[tuple[str, list[str], dict[str, Any]]]) -> None:
        self.graph.upsert_nodes_batch([(node_id, props, labels[0]) for node_id, labels, props in nodes])

    def upsert_edge(self, source_id: str, target_id: str, rel_type: str, props: dict[str, Any]) -> None:
        self.graph.upsert_edge(source_id, target_id, props, rel_type=rel_type)

    def upsert_edges(self, edges: list[tuple[str, str, str, dict[str, Any]]]) -> None:
        self.graph.upsert_edges_batch([(source_id, target_id, props, rel_type) for source_id, target_id, rel_type, props in edges])

    def insert_graph(
        self,
        nodes: list[tuple[str, list[str], dict[str, Any]]],
        edges: list[tuple[str, str, str, dict[str, Any]]],
    ) -> None:
        self.graph.insert_graph_bulk(
            [(node_id, props, labels[0]) for node_id, labels, props in nodes],
            [(source_id, target_id, props, rel_type) for source_id, target_id, rel_type, props in edges],
        )

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        node = self.graph.get_node(node_id)
        return _normalize_graphqlite_node(node) if node is not None else None

    def get_all_nodes(self, label: str | None = None) -> list[dict[str, Any]]:
        rows = [_normalize_graphqlite_node(row) for row in self.graph.get_all_nodes(label=label)]
        if label is None:
            return rows
        return [row for row in rows if label in _node_labels(row)]

    def get_all_edges(self) -> list[dict[str, Any]]:
        return [_normalize_graphqlite_edge(edge) for edge in self.graph.get_all_edges()]

    def delete_node(self, node_id: str) -> None:
        self.graph.delete_node(node_id)

    def delete_edge(self, source_id: str, target_id: str, rel_type: str | None = None) -> None:
        self.graph.delete_edge(source_id, target_id, rel_type=rel_type)

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.graph.query(cypher, params or {})

    def stats(self) -> dict[str, int]:
        raw = self.graph.stats()
        return {"node_count": int(raw.get("node_count", 0)), "edge_count": int(raw.get("edge_count", 0))}

    def count_nodes(self, label: str | None = None, props: dict[str, Any] | None = None) -> int:
        label_clause = f":{_safe_identifier(label)}" if label else ""
        params = _clean_props(props or {})
        where = ""
        if params:
            where = " WHERE " + " AND ".join(f"n.{_safe_identifier(key)} = ${key}" for key in params)
        rows = self.graph.query(f"MATCH (n{label_clause}){where} RETURN count(n) AS count", params)
        return int(rows[0]["count"]) if rows else 0

    def count_edges(self, rel_type: str | None = None) -> int:
        rel_clause = f":{_safe_rel_type(rel_type)}" if rel_type else ""
        rows = self.graph.query(f"MATCH ()-[r{rel_clause}]->() RETURN count(r) AS count")
        return int(rows[0]["count"]) if rows else 0


class _SqliteGraphBackend:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    node_id TEXT PRIMARY KEY,
                    primary_label TEXT NOT NULL,
                    labels_json TEXT NOT NULL,
                    props_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS graph_edges (
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    rel_type TEXT NOT NULL,
                    props_json TEXT NOT NULL,
                    PRIMARY KEY (source_id, target_id, rel_type)
                );
                """
            )

    def upsert_node(self, node_id: str, labels: list[str], props: dict[str, Any]) -> None:
        existing = self.get_node(node_id)
        merged = {**(existing or {}), **props}
        merged.pop("_id", None)
        merged.pop("_label", None)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO graph_nodes (node_id, primary_label, labels_json, props_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    primary_label = excluded.primary_label,
                    labels_json = excluded.labels_json,
                    props_json = excluded.props_json
                """,
                (node_id, labels[0], _json(labels), _json(merged)),
            )

    def upsert_nodes(self, nodes: list[tuple[str, list[str], dict[str, Any]]]) -> None:
        for node_id, labels, props in nodes:
            self.upsert_node(node_id, labels, props)

    def upsert_edge(self, source_id: str, target_id: str, rel_type: str, props: dict[str, Any]) -> None:
        existing = self._get_edge(source_id, target_id, rel_type)
        merged = {**(existing or {}), **props}
        for key in ("_src", "_dst", "_rel_type"):
            merged.pop(key, None)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO graph_edges (source_id, target_id, rel_type, props_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_id, target_id, rel_type) DO UPDATE SET
                    props_json = excluded.props_json
                """,
                (source_id, target_id, rel_type, _json(merged)),
            )

    def upsert_edges(self, edges: list[tuple[str, str, str, dict[str, Any]]]) -> None:
        for source_id, target_id, rel_type, props in edges:
            self.upsert_edge(source_id, target_id, rel_type, props)

    def insert_graph(
        self,
        nodes: list[tuple[str, list[str], dict[str, Any]]],
        edges: list[tuple[str, str, str, dict[str, Any]]],
    ) -> None:
        self.upsert_nodes(nodes)
        self.upsert_edges(edges)

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT node_id, primary_label, labels_json, props_json FROM graph_nodes WHERE node_id = ?",
                (node_id,),
            ).fetchone()
        return _sqlite_node(row) if row is not None else None

    def get_all_nodes(self, label: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT node_id, primary_label, labels_json, props_json FROM graph_nodes ORDER BY node_id"
            ).fetchall()
        nodes = [_sqlite_node(row) for row in rows]
        if label is None:
            return nodes
        return [node for node in nodes if label in _node_labels(node)]

    def get_all_edges(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT source_id, target_id, rel_type, props_json FROM graph_edges ORDER BY source_id, target_id, rel_type"
            ).fetchall()
        return [_sqlite_edge(row) for row in rows]

    def delete_node(self, node_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM graph_edges WHERE source_id = ? OR target_id = ?", (node_id, node_id))
            conn.execute("DELETE FROM graph_nodes WHERE node_id = ?", (node_id,))

    def delete_edge(self, source_id: str, target_id: str, rel_type: str | None = None) -> None:
        with self._connect() as conn:
            if rel_type is None:
                conn.execute("DELETE FROM graph_edges WHERE source_id = ? AND target_id = ?", (source_id, target_id))
            else:
                conn.execute(
                    "DELETE FROM graph_edges WHERE source_id = ? AND target_id = ? AND rel_type = ?",
                    (source_id, target_id, rel_type),
                )

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError("Cypher queries require the GraphQLite backend.")

    def stats(self) -> dict[str, int]:
        with self._connect() as conn:
            node_count = conn.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
            edge_count = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
        return {"node_count": int(node_count), "edge_count": int(edge_count)}

    def count_nodes(self, label: str | None = None, props: dict[str, Any] | None = None) -> int:
        nodes = self.get_all_nodes(label)
        if props:
            nodes = [node for node in nodes if all(node.get(key) == value for key, value in props.items())]
        return len(nodes)

    def count_edges(self, rel_type: str | None = None) -> int:
        return len([edge for edge in self.get_all_edges() if rel_type is None or edge.get("_rel_type") == rel_type or edge.get("rel_type") == rel_type])

    def _get_edge(self, source_id: str, target_id: str, rel_type: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT source_id, target_id, rel_type, props_json
                FROM graph_edges
                WHERE source_id = ? AND target_id = ? AND rel_type = ?
                """,
                (source_id, target_id, rel_type),
            ).fetchone()
        return _sqlite_edge(row) if row is not None else None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


def _clean_labels(labels: Iterable[str]) -> list[str]:
    clean = [label.strip() for label in labels if label.strip()]
    return clean or ["Entity"]


def _clean_props(props: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): _json_safe(value)
        for key, value in props.items()
        if value not in ("", None, {}, [])
    }


def _dedupe_node_buffer(nodes: list[tuple[str, list[str], dict[str, Any]]]) -> list[tuple[str, list[str], dict[str, Any]]]:
    merged: dict[str, tuple[list[str], dict[str, Any]]] = {}
    for node_id, labels, props in nodes:
        if node_id not in merged:
            merged[node_id] = (labels, dict(props))
            continue
        existing_labels, existing_props = merged[node_id]
        combined_labels = list(dict.fromkeys([*existing_labels, *labels]))
        existing_props.update(props)
        merged[node_id] = (combined_labels, existing_props)
    return [(node_id, labels, props) for node_id, (labels, props) in merged.items()]


def _dedupe_edge_buffer(edges: list[tuple[str, str, str, dict[str, Any]]]) -> list[tuple[str, str, str, dict[str, Any]]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    preserved: list[tuple[str, str, str, dict[str, Any]]] = []
    for source_id, target_id, rel_type, props in edges:
        if rel_type == "USES_EVIDENCE":
            preserved.append((source_id, target_id, rel_type, props))
            continue
        key = (source_id, target_id, rel_type)
        merged.setdefault(key, {}).update(props)
    preserved.extend((source_id, target_id, rel_type, props) for (source_id, target_id, rel_type), props in merged.items())
    return preserved


def _safe_identifier(value: str | None) -> str:
    raw = str(value or "")
    clean = "".join(char if char.isalnum() or char == "_" else "_" for char in raw)
    if not clean:
        raise ValueError("identifier must not be empty")
    return clean


def _safe_rel_type(value: str | None) -> str:
    raw = str(value or "")
    if raw == "ON":
        raw = "REL_ON"
    return _safe_identifier(raw)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _node_labels(node: dict[str, Any]) -> list[str]:
    labels = node.get("labels")
    if isinstance(labels, list):
        return [str(label) for label in labels]
    label = node.get("_label")
    return [str(label)] if label else []


def _sqlite_node(row: sqlite3.Row) -> dict[str, Any]:
    labels = _json_array(str(row["labels_json"]))
    props = _json_dict(str(row["props_json"]))
    props["_id"] = str(row["node_id"])
    props["_label"] = str(row["primary_label"])
    props["labels"] = labels
    return props


def _sqlite_edge(row: sqlite3.Row) -> dict[str, Any]:
    props = _json_dict(str(row["props_json"]))
    props["_src"] = str(row["source_id"])
    props["_dst"] = str(row["target_id"])
    props["_rel_type"] = str(row["rel_type"])
    props["rel_type"] = str(row["rel_type"])
    return props


def _normalize_graphqlite_edge(edge: dict[str, Any]) -> dict[str, Any]:
    rel = edge.get("r")
    rel_payload = rel if isinstance(rel, dict) else {}
    props = rel_payload.get("properties")
    normalized = dict(props) if isinstance(props, dict) else dict(edge)
    if "_src" not in normalized:
        normalized["_src"] = str(edge.get("source") or edge.get("src") or edge.get("source_id") or "")
    if "_dst" not in normalized:
        normalized["_dst"] = str(edge.get("target") or edge.get("dst") or edge.get("target_id") or "")
    if "_rel_type" not in normalized:
        normalized["_rel_type"] = str(normalized.get("rel_type") or rel_payload.get("type") or edge.get("rel_type") or edge.get("_type") or "")
    normalized["rel_type"] = str(normalized.get("rel_type") or normalized["_rel_type"])
    return normalized


def _normalize_graphqlite_node(node: dict[str, Any]) -> dict[str, Any]:
    props = node.get("properties")
    normalized = dict(props) if isinstance(props, dict) else dict(node)
    labels = node.get("labels") or normalized.get("labels") or []
    if not isinstance(labels, list):
        labels = [str(labels)]
    normalized["labels"] = [str(label) for label in labels]
    normalized["_label"] = normalized["labels"][0] if normalized["labels"] else str(node.get("label") or "")
    normalized["_id"] = str(normalized.get("node_id") or normalized.get("id") or node.get("id") or "")
    if "id" in node:
        normalized["_internal_id"] = node["id"]
    return normalized


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_dict(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_array(value: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []
