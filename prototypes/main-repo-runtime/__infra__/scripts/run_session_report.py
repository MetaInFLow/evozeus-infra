from __future__ import annotations

import argparse
from pathlib import Path

from evozeus.runtime.analysis_service import analyze_session, scan_sessions
from evozeus.scanners.base import SessionRef


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="")
    parser.add_argument("--pack-root", default=str(PROJECT_ROOT / "__infra__" / "factor_packs"))
    parser.add_argument("--workspace", default=str(PROJECT_ROOT))
    parser.add_argument("--factor", action="append", default=[])
    parser.add_argument("--session-id", default="")
    parser.add_argument("--session-index", type=int, default=0)
    args = parser.parse_args()

    scan_summary = scan_sessions(
        workspace_root=Path(args.workspace),
        source_dir=Path(args.source) if args.source else None,
    )
    assert scan_summary.refs, "no sessions found"
    session_id = _select_session_id(scan_summary.refs, args.session_id, args.session_index)
    analysis_summary = analyze_session(
        workspace_root=Path(args.workspace),
        session_id=session_id,
        factor_ids=args.factor or None,
        pack_root=Path(args.pack_root),
    )
    assert analysis_summary.error_count == 0
    assert analysis_summary.result_count > 0, "expected factor results"

    print(
        "session report ok: "
        f"session_id={analysis_summary.session_id} "
        f"results={analysis_summary.result_count} "
        f"analysis_run_id={analysis_summary.analysis_run_id} "
        f"sqlite={analysis_summary.sqlite_path} "
        f"md={analysis_summary.markdown_path} "
        f"html={analysis_summary.html_path}"
    )


def _select_session_id(refs: list[SessionRef], session_id: str, session_index: int) -> str:
    if session_id:
        return session_id
    if session_index < 0 or session_index >= len(refs):
        raise AssertionError(f"session index out of range: {session_index}")
    return refs[session_index].session_id


if __name__ == "__main__":
    main()
