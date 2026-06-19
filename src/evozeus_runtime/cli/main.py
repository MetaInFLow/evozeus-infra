from __future__ import annotations

from pathlib import Path

import typer

from evozeus_runtime import __version__
from evozeus_runtime.use_cases.generate_report import generate_report
from evozeus_runtime.use_cases.run_factors import run_factors
from evozeus_runtime.use_cases.scan_sessions import scan_sessions

app = typer.Typer(help="EvoZeus local scanner and factor runner runtime.")


@app.command()
def status() -> None:
    typer.echo(f"evozeus-runtime {__version__}: scanner-runner-runtime")


@app.command()
def scan(
    provider: str = typer.Option("codex", "--provider"),
    source: Path | None = typer.Option(None, "--source"),
    workspace: Path = typer.Option(Path("."), "--workspace", help="Workspace root for .evozeus state. Defaults to cwd."),
) -> None:
    result = scan_sessions(workspace_root=workspace, provider=provider, source_dir=source)
    typer.echo(f"scanned_sessions={result.session_count}")
    typer.echo(f"ledger={result.ledger_path}")


@app.command()
def run(
    session_id: str = typer.Option(..., "--session-id"),
    factor: list[str] = typer.Option(..., "--factor"),
    pack_root: Path = typer.Option(..., "--pack-root"),
    workspace: Path = typer.Option(Path("."), "--workspace", help="Workspace root for .evozeus state. Defaults to cwd."),
) -> None:
    result = run_factors(
        workspace_root=workspace,
        session_id=session_id,
        factor_ids=factor,
        pack_root=pack_root,
    )
    typer.echo(f"results={result.result_count}")
    typer.echo(f"errors={result.error_count}")
    typer.echo(f"analysis_run_id={result.analysis_run_id}")


@app.command()
def report(
    session_id: str = typer.Option(..., "--session-id"),
    format: list[str] = typer.Option(["markdown"], "--format"),
    workspace: Path = typer.Option(Path("."), "--workspace", help="Workspace root for .evozeus state. Defaults to cwd."),
) -> None:
    result = generate_report(workspace_root=workspace, session_id=session_id, formats=format)
    typer.echo(f"markdown={result.markdown_path}")
    typer.echo(f"json={result.json_path}")
    typer.echo(f"html={result.html_path}")


if __name__ == "__main__":
    app()
