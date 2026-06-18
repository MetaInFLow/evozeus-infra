from __future__ import annotations

import tempfile
from pathlib import Path

from evozeus.factors.base import FactorContext
from evozeus.factors.packs import FactorPackRepository
from evozeus.factors.runner import FactorRunner
from evozeus.runtime.paths import RuntimePaths
from evozeus.storage.file_repository import FileSessionRepository
from smoke_support import sample_session


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = RuntimePaths.for_workspace(Path(tmp)).ensure()
        repository = FileSessionRepository(paths)
        factor_repository = FactorPackRepository(PROJECT_ROOT / "__infra__" / "factor_packs")
        packs = factor_repository.discover()
        factor = factor_repository.load("default.tool_failure")
        session = sample_session()
        summary = FactorRunner([factor]).run(FactorContext(session=session))
        assert summary.results
        repository.write_session(session)
        repository.append_factor_results(session.session_id, summary.results)
        html_path = repository.write_factor_results_html(session.session_id, summary.results, packs)

        session_dir = paths.session_dir(session.session_id)
        report_path = session_dir / "factor-results.md"
        jsonl_path = session_dir / "factor-results.jsonl"
        json_path = session_dir / "factor-results.json"
        assert report_path.exists()
        assert html_path.exists()
        assert "default.tool_failure" in report_path.read_text(encoding="utf-8")
        assert "default.tool_failure" in html_path.read_text(encoding="utf-8")
        assert not jsonl_path.exists()
        assert not json_path.exists()
        print(
            "result report ok: "
            f"paths={report_path.name},{html_path.name} "
            f"json_result_file={jsonl_path.exists() or json_path.exists()}"
        )


if __name__ == "__main__":
    main()
