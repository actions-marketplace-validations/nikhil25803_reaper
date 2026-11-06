"""Command-line interface and executable entry point for Reaper."""

from pathlib import Path
from typing import Annotated

import typer

from reaper import __version__
from reaper.analysis_cli import analyze
from reaper.graph_cli import graph_app
from reaper.utils.graphify import run_graphify_check, run_graphify_scan

DESCRIPTION = "Reaper is a language-agnostic tool for dead code detection and analysis."

app = typer.Typer(
    add_completion=False,
    help=DESCRIPTION,
    invoke_without_command=True,
    name="reaper",
    no_args_is_help=False,
)
app.add_typer(graph_app, name="graph")
app.command()(analyze)


def version_callback(value: bool) -> None:
    """Print the package version and exit."""
    if value:
        typer.echo(__version__)
        raise typer.Exit


@app.callback()
def _callback(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
    check: Annotated[
        str | None,
        typer.Option("--check", metavar="TOOL", help="Check an external tool."),
    ] = None,
    scan: Annotated[
        Path | None,
        typer.Option(
            "--scan",
            exists=True,
            file_okay=False,
            readable=True,
            resolve_path=True,
            help="Generate a code graph for a project directory.",
        ),
    ] = None,
) -> None:
    """Detect potentially unused code in software projects."""
    if check is not None and scan is not None:
        raise typer.BadParameter("--check and --scan cannot be used together")
    if check is not None:
        run_graphify_check(check)
    elif scan is not None:
        run_graphify_scan(scan)
    elif ctx.invoked_subcommand is None and not version:
        typer.echo(ctx.get_help())


def main() -> None:
    """Run the Reaper CLI."""
    app()


if __name__ == "__main__":
    main()
