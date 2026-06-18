from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from evozeus.companion.tokens import token_matches


def create_app(token: str, workspace_root: Path | None = None) -> FastAPI:
    app = FastAPI(title="EvoZeus Companion")
    root = workspace_root or Path.cwd()

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> str:
        _require_token(token, request.query_params.get("token"))
        return "<h1>EvoZeus Companion</h1><p>Review required.</p>"

    @app.get("/api/bootstrap/status")
    def bootstrap_status(request: Request) -> dict[str, object]:
        _require_token(token, request.query_params.get("token"))
        config_path = root / ".evozeus" / "config.json"
        db_path = root / ".evozeus" / "runtime" / "index" / "results.sqlite3"
        return {
            "initialized": config_path.exists() and db_path.exists(),
            "workspace": str(root / ".evozeus"),
            "sqlite": str(db_path),
        }

    @app.post("/api/bootstrap")
    def bootstrap(request: Request) -> dict[str, object]:
        _require_token(token, request.query_params.get("token"))
        store = _bootstrap_workspace(root)
        return {
            "initialized": True,
            "workspace": str(root / ".evozeus"),
            "sqlite": str(store.db_path),
            "installed_factor_count": len(store.list_installed_factors()),
        }

    @app.get("/api/factors")
    def factors(request: Request) -> dict[str, object]:
        _require_token(token, request.query_params.get("token"))
        store = _store(root)
        return {"factors": [asdict(factor) for factor in store.list_installed_factors()]}

    @app.get("/api/routes")
    def routes(request: Request) -> dict[str, object]:
        _require_token(token, request.query_params.get("token"))
        store = _store(root)
        return {"routes": [asdict(route) for route in store.list_factor_result_routes()]}

    @app.get("/api/sessions")
    def sessions(
        request: Request,
        factor_id: list[str] | None = Query(default=None),
    ) -> dict[str, object]:
        _require_token(token, request.query_params.get("token"))
        store = _store(root)
        return {"sessions": [asdict(session) for session in store.list_session_statuses(factor_ids=factor_id)]}

    @app.post("/api/scan")
    def scan(
        request: Request,
        source: str = "",
        limit: int | None = None,
    ) -> dict[str, object]:
        _require_token(token, request.query_params.get("token"))
        from evozeus.runtime.analysis_service import scan_sessions

        summary = scan_sessions(
            workspace_root=root,
            source_dir=Path(source) if source else None,
            limit=limit,
        )
        return {
            "session_count": summary.session_count,
            "session_ids": [ref.session_id for ref in summary.refs],
            "sqlite": str(summary.sqlite_path),
        }

    @app.post("/api/analyze/{session_id}")
    def analyze(
        session_id: str,
        request: Request,
        factor_id: list[str] | None = Query(default=None),
    ) -> dict[str, object]:
        _require_token(token, request.query_params.get("token"))
        from evozeus.runtime.analysis_service import analyze_session

        summary = analyze_session(
            workspace_root=root,
            session_id=session_id,
            factor_ids=factor_id,
        )
        return {
            "session_id": summary.session_id,
            "result_count": summary.result_count,
            "error_count": summary.error_count,
            "analysis_run_id": summary.analysis_run_id,
            "sqlite": str(summary.sqlite_path),
            "markdown_path": str(summary.markdown_path),
            "html_path": str(summary.html_path),
        }

    return app


def _require_token(expected: str, provided: str | None) -> None:
    if not token_matches(expected, provided):
        raise HTTPException(status_code=403, detail="Invalid token")


def _store(root: Path):
    from evozeus.runtime.paths import RuntimePaths
    from evozeus.storage.sqlite_result_store import SQLiteResultStore

    return SQLiteResultStore(RuntimePaths.for_workspace(root).ensure())


def _bootstrap_workspace(root: Path):
    from evozeus.factors.packs import FactorPackRepository
    from evozeus.workspace import create_workspace

    create_workspace(root)
    store = _store(root)
    pack_root = Path(__file__).resolve().parents[3] / "factor_packs"
    packs = FactorPackRepository(pack_root).discover()
    store.record_installed_factors(packs, source="bundled")
    store.record_default_routes(packs)
    return store
