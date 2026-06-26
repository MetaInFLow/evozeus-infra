from __future__ import annotations

from pathlib import Path

import typer

from evozeus_runtime import __version__
from evozeus_runtime.ledger.graph_repository import GraphQLiteNotInstalledError
from evozeus_runtime.ledger.migrate_sqlite_to_graphqlite import migrate_workspace_sqlite_to_graphqlite
from evozeus_runtime.use_cases.generate_graph_ledger_browser import generate_graph_ledger_browser
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
    workspace: Path = typer.Option(Path.home(), "--workspace", help="Workspace root for .evozeus state. Defaults to home."),
) -> None:
    result = scan_sessions(workspace_root=workspace, provider=provider, source_dir=source)
    typer.echo(f"scanned_sessions={result.session_count}")
    typer.echo(f"ledger={result.ledger_path}")


@app.command()
def run(
    session_id: str = typer.Option(..., "--session-id"),
    factor: list[str] = typer.Option(..., "--factor"),
    pack_root: Path = typer.Option(..., "--pack-root"),
    workspace: Path = typer.Option(Path.home(), "--workspace", help="Workspace root for .evozeus state. Defaults to home."),
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
    workspace: Path = typer.Option(Path.home(), "--workspace", help="Workspace root for .evozeus state. Defaults to home."),
) -> None:
    result = generate_report(workspace_root=workspace, session_id=session_id, formats=format)
    typer.echo(f"markdown={result.markdown_path}")
    typer.echo(f"json={result.json_path}")
    typer.echo(f"html={result.html_path}")


@app.command("migrate-ledger")
def migrate_ledger(
    workspace: Path = typer.Option(Path.home(), "--workspace", help="Workspace root for .evozeus state. Defaults to home."),
    legacy_db: Path | None = typer.Option(None, "--legacy-db", help="Legacy SQLite ledger path. Defaults to workspace results.sqlite3."),
    output: Path | None = typer.Option(None, "--output", help="Graph ledger output path. Defaults to results.graph.sqlite3."),
    no_backup: bool = typer.Option(False, "--no-backup", help="Do not copy results.sqlite3 to results.sqlite3.legacy."),
) -> None:
    try:
        result = migrate_workspace_sqlite_to_graphqlite(
            workspace_root=workspace,
            legacy_db_path=legacy_db,
            output_db_path=output,
            backup=not no_backup,
        )
    except GraphQLiteNotInstalledError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    typer.echo(f"migration_id={result.migration_id}")
    typer.echo(f"legacy={result.legacy_db_path}")
    typer.echo(f"graph={result.output_db_path}")
    if result.backup_db_path is not None:
        typer.echo(f"backup={result.backup_db_path}")
    for check in result.checks:
        status = "ok" if check.ok else "failed"
        typer.echo(
            f"check={check.name} legacy={check.legacy_count} graph={check.graph_count} "
            f"op={check.operator} status={status}"
        )
    if not result.ok:
        raise typer.Exit(1)


@app.command("graph-browser")
def graph_browser(
    workspace: Path = typer.Option(Path.home(), "--workspace", help="Workspace root for .evozeus state. Defaults to home."),
    graph: Path | None = typer.Option(None, "--graph", help="GraphQLite ledger path. Defaults to results.graph.sqlite3."),
    legacy: Path | None = typer.Option(None, "--legacy", help="Legacy SQLite ledger path. Defaults to results.sqlite3."),
    output: Path | None = typer.Option(None, "--output", help="HTML output path. Defaults to evozeus-graph.html."),
) -> None:
    result = generate_graph_ledger_browser(
        workspace_root=workspace,
        graph_path=graph,
        legacy_path=legacy,
        output_path=output,
    )
    typer.echo(f"html={result.html_path}")
    typer.echo(f"graph={result.graph_path}")
    typer.echo(f"legacy={result.legacy_path}")
    typer.echo(f"nodes={result.node_count}")
    typer.echo(f"edges={result.edge_count}")


if __name__ == "__main__":
    app()
