"""Model-assisted dead-code analysis command."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from reaper.graph_cli import project_graph
from reaper.utils.analysis import (
    build_report,
    candidate_evidence,
    merge_findings,
    write_refactoring_prompt,
    write_reports,
)
from reaper.utils.graph import analysis_candidates
from reaper.utils.graphify import run_graphify_scan
from reaper.utils.llama import LlamaClient, LlamaError

BATCH_SIZE = 4


def prompt(
    project: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            readable=True,
            resolve_path=True,
            metavar="PROJECT_PATH",
            help="Project directory containing a Reaper analysis report.",
        ),
    ] = Path("."),
) -> None:
    """Generate a model-neutral refactoring prompt from an analysis report."""
    try:
        prompt_path = write_refactoring_prompt(project)
    except (OSError, ValueError) as error:
        typer.echo(f"Unable to generate refactoring prompt: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"Refactoring prompt: {prompt_path}")


def analyze(
    project: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            readable=True,
            resolve_path=True,
            metavar="PROJECT_PATH",
            help="Project directory to analyze.",
        ),
    ] = Path("."),
    scan: Annotated[
        bool, typer.Option("--scan", help="Refresh the Graphify graph first.")
    ] = False,
    server: Annotated[
        str,
        typer.Option(help="llama-server base URL."),
    ] = "http://127.0.0.1:8080",
    model: Annotated[
        str | None,
        typer.Option(help="Loaded llama.cpp model ID."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option(
            min=1,
            help="Maximum candidates to review; defaults to 20.",
        ),
    ] = None,
    all_: Annotated[
        bool, typer.Option("--all", help="Review the complete candidate pool.")
    ] = False,
    low_connectivity: Annotated[
        int | None,
        typer.Option(
            "--low-connectivity",
            min=0,
            metavar="CONNECTIONS",
            help="Review nodes with at most this many total usage connections.",
        ),
    ] = None,
    timeout: Annotated[
        int, typer.Option(min=1, help="llama-server timeout in seconds.")
    ] = 300,
) -> None:
    """Review graph candidates with a local llama.cpp model."""
    if all_ and limit is not None:
        raise typer.BadParameter("--all and --limit cannot be used together")

    if scan:
        run_graphify_scan(project)
    nodes, edges = project_graph(project)
    pool = analysis_candidates(nodes, edges, low_connectivity)
    effective_limit = None if all_ else (limit or 20)
    selected = pool if effective_limit is None else pool[:effective_limit]

    evidence: list[dict] = []
    try:
        for node, incoming, outgoing in selected:
            evidence.append(
                candidate_evidence(
                    project,
                    node,
                    edges,
                    nodes,
                    incoming,
                    outgoing,
                )
            )
    except ValueError as error:
        typer.echo(f"Unable to prepare analysis evidence: {error}", err=True)
        raise typer.Exit(1) from error

    selected_model: str | None = None
    verdicts: list[dict] = []
    if evidence:
        try:
            client = LlamaClient(server, timeout)
            client.check_health()
            selected_model = client.select_model(model)
            typer.echo(
                f"Reviewing {len(evidence)} of {len(pool)} ranked callable(s) "
                f"with {selected_model}..."
            )
            for start in range(0, len(evidence), BATCH_SIZE):
                verdicts.extend(
                    client.analyze_batch(
                        selected_model,
                        evidence[start : start + BATCH_SIZE],
                    )
                )
        except LlamaError as error:
            typer.echo(f"llama.cpp analysis failed: {error}", err=True)
            raise typer.Exit(1) from error

    findings = merge_findings(evidence, verdicts) if evidence else []
    report = build_report(
        project,
        selected_model,
        findings,
        len(evidence),
        effective_limit,
        low_connectivity,
    )
    try:
        json_path, markdown_path = write_reports(project, report)
    except OSError as error:
        typer.echo(f"Unable to write analysis reports: {error}", err=True)
        raise typer.Exit(1) from error
    _render_report(report, project, json_path, markdown_path)


def _render_report(
    report: dict,
    project: Path,
    json_path: Path,
    markdown_path: Path,
) -> None:
    console = Console()
    summary = report["summary"]
    table = Table(title="Reaper <> llama.cpp Analysis Complete")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Reviewed", str(summary["reviewed"]))
    table.add_row("Likely dead", str(summary["likely_dead"]))
    table.add_row("Needs review", str(summary["needs_review"]))
    table.add_row("Likely used", str(summary["likely_used"]))
    console.print(table)

    actionable = [
        finding
        for finding in report["findings"]
        if finding["verdict"] in {"likely_dead", "needs_review"}
    ]
    if actionable:
        console.print()
        findings_table = Table(title="Model-Assisted Findings")
        findings_table.add_column("Verdict")
        findings_table.add_column("Confidence", justify="right")
        findings_table.add_column("Symbol")
        findings_table.add_column("Source", overflow="fold")
        findings_table.add_column("Line")
        findings_table.add_column("Reason", overflow="fold")
        for finding in actionable:
            verdict = (
                "Likely dead" if finding["verdict"] == "likely_dead" else "Needs review"
            )
            findings_table.add_row(
                verdict,
                f"{finding['confidence']}%",
                finding["symbol"],
                finding["source"],
                finding["line"],
                finding["reason"],
            )
        console.print(findings_table)
        typer.echo()
        typer.echo(
            f'Inspect: reaper graph inspect "{project}" "{actionable[0]["node_id"]}"'
        )
    elif summary["reviewed"]:
        typer.echo(
            "No actionable findings; all reviewed candidates appear likely used."
        )
    else:
        typer.echo("No candidates matched the selected graph criteria.")

    typer.echo(f"JSON report: {json_path}")
    typer.echo(f"Markdown report: {markdown_path}")
