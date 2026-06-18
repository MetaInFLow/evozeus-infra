from __future__ import annotations

from pathlib import Path

import typer

from evozeus import __version__
from evozeus.checks import current_branch_name, validate_branch_name

app = typer.Typer(help="EvoZeus local judgment workbench.")


@app.command()
def version() -> None:
    """Print EvoZeus version."""
    typer.echo(__version__)


@app.command()
def status() -> None:
    """Print local EvoZeus status."""
    typer.echo("EvoZeus status: manual-session-review")


@app.command()
def onboard() -> None:
    """Run first-time setup checks."""
    from evozeus.factors.packs import FactorPackRepository
    from evozeus.runtime.paths import RuntimePaths
    from evozeus.storage.sqlite_result_store import SQLiteResultStore
    from evozeus.workspace import create_workspace

    cwd = Path.cwd()
    workspace = create_workspace(cwd)
    paths = RuntimePaths.for_workspace(cwd).ensure()
    store = SQLiteResultStore(paths)
    pack_root = Path(__file__).resolve().parents[2] / "factor_packs"
    packs = FactorPackRepository(pack_root).discover()
    store.record_installed_factors(packs, source="bundled")
    store.record_default_routes(packs)

    typer.echo("EvoZeus onboard: local-first, zero-upload")
    typer.echo(f"workspace={workspace.root}")
    typer.echo(f"sqlite={paths.result_index_db}")
    typer.echo(f"installed_factors={len(packs)}")


@app.command()
def doctor(evidence: str = typer.Option("", "--evidence")) -> None:
    """Run lightweight debug diagnosis."""
    if evidence:
        from evozeus.doctor import classify_failure

        typer.echo(f"EvoZeus doctor verdict: {classify_failure(evidence).value}")
        return
    typer.echo("EvoZeus doctor: collect evidence before changes")


@app.command()
def check(branch: str = typer.Option("", "--branch")) -> None:
    """Run basic pre-upload checks."""
    branch_name = branch or current_branch_name()
    result = validate_branch_name(branch_name)
    typer.echo(result.message)
    if not result.ok:
        raise typer.Exit(1)


@app.command()
def tui(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    """Open the TUI."""
    if dry_run:
        typer.echo("Current Session | Debug Verdicts | Case Drafts | Skill Proposals | Factor Runtime | History")
        return
    from evozeus.tui.app import EvoZeusApp

    EvoZeusApp().run()
