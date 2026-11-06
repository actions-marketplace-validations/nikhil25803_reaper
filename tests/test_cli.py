import json
import subprocess
import sys

from typer.testing import CliRunner

from reaper import __version__
from reaper.main import app

runner = CliRunner()


def write_graph(project, graph: object) -> None:
    graph_dir = project / "reaper-analysis" / "graphify-out"
    graph_dir.mkdir(parents=True)
    (graph_dir / "graph.json").write_text(json.dumps(graph), encoding="utf-8")


def test_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Reaper" in result.output
    assert "dead code detection and analysis" in result.output


def test_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__ == "0.1.0"


def test_no_arguments_displays_help() -> None:
    result = runner.invoke(app)

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "help" in result.output.lower()


def test_check_graphify(monkeypatch) -> None:
    monkeypatch.setattr(
        "reaper.utils.graphify.shutil.which", lambda _: "/usr/bin/graphify"
    )
    monkeypatch.setattr(
        "reaper.utils.graphify.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout="graphify 0.9.95\n", stderr=""
        ),
    )

    result = runner.invoke(app, ["--check", "graphify"])

    assert result.exit_code == 0
    assert result.output.strip() == "graphify 0.9.95"


def test_check_graphify_when_missing(monkeypatch) -> None:
    monkeypatch.setattr("reaper.utils.graphify.shutil.which", lambda _: None)

    result = runner.invoke(app, ["--check", "graphify"])

    assert result.exit_code == 1
    assert "uv tool install graphifyy" in result.output


def test_check_rejects_unknown_tool() -> None:
    result = runner.invoke(app, ["--check", "other"])

    assert result.exit_code == 2
    assert "only graphify is supported" in result.output


def test_scan_invokes_graphify(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "reaper.utils.graphify.shutil.which", lambda _: "/usr/bin/graphify"
    )

    def run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        write_graph(
            project,
            {
                "nodes": [
                    {"community": 1},
                    {"community": 1},
                    {"community": 2},
                ],
                "links": [{}, {}],
            },
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="verbose graphify output\n",
            stderr="graphify warning\n",
        )

    monkeypatch.setattr("reaper.utils.graphify.subprocess.run", run)

    result = runner.invoke(app, ["--scan", str(project)])

    resolved_project = project.resolve()
    assert result.exit_code == 0
    assert "Reaper <> Graphify Scan Complete" in " ".join(result.output.split())
    assert commands == [
        [
            "/usr/bin/graphify",
            "extract",
            str(resolved_project),
            "--out",
            str(resolved_project / "reaper-analysis"),
            "--code-only",
        ]
    ]
    assert "Nodes" in result.output
    assert "3" in result.output
    assert "Edges" in result.output
    assert "2" in result.output
    assert "Communities" in result.output
    assert "verbose graphify output" not in result.output
    assert "graphify warning" not in result.output
    assert "reaper-analysis" not in result.output


def test_scan_reads_legacy_edges(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "reaper.utils.graphify.shutil.which", lambda _: "/usr/bin/graphify"
    )

    def run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        write_graph(tmp_path, {"nodes": [{"community": 0}], "edges": [{}]})
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("reaper.utils.graphify.subprocess.run", run)

    result = runner.invoke(app, ["--scan", str(tmp_path)])

    assert result.exit_code == 0
    assert "Edges" in result.output
    assert "1" in result.output


def test_scan_rejects_missing_directory(tmp_path) -> None:
    result = runner.invoke(app, ["--scan", str(tmp_path / "missing")])

    assert result.exit_code == 2


def test_scan_propagates_graphify_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "reaper.utils.graphify.shutil.which", lambda _: "/usr/bin/graphify"
    )
    monkeypatch.setattr(
        "reaper.utils.graphify.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            7,
            stdout="scan progress\n",
            stderr="scan failed\n",
        ),
    )

    result = runner.invoke(app, ["--scan", str(tmp_path)])

    assert result.exit_code == 7
    assert "scan progress" in result.output
    assert "scan failed" in result.output


def test_scan_requires_graph_output(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "reaper.utils.graphify.shutil.which", lambda _: "/usr/bin/graphify"
    )
    monkeypatch.setattr(
        "reaper.utils.graphify.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout="", stderr=""
        ),
    )

    result = runner.invoke(app, ["--scan", str(tmp_path)])

    assert result.exit_code == 1
    assert "graph.json was not created" in result.output


def test_scan_rejects_malformed_graph(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "reaper.utils.graphify.shutil.which", lambda _: "/usr/bin/graphify"
    )
    graph_dir = tmp_path / "reaper-analysis" / "graphify-out"
    graph_dir.mkdir(parents=True)
    (graph_dir / "graph.json").write_text("not json", encoding="utf-8")
    monkeypatch.setattr(
        "reaper.utils.graphify.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout="", stderr=""
        ),
    )

    result = runner.invoke(app, ["--scan", str(tmp_path)])

    assert result.exit_code == 1
    assert "Unable to read Graphify output" in result.output


def test_scan_rejects_invalid_graph_structure(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "reaper.utils.graphify.shutil.which", lambda _: "/usr/bin/graphify"
    )
    write_graph(tmp_path, {"nodes": {}, "links": []})
    monkeypatch.setattr(
        "reaper.utils.graphify.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout="", stderr=""
        ),
    )

    result = runner.invoke(app, ["--scan", str(tmp_path)])

    assert result.exit_code == 1
    assert "invalid graph.json" in result.output


def test_check_and_scan_are_mutually_exclusive() -> None:
    result = runner.invoke(app, ["--check", "graphify", "--scan", "."])

    assert result.exit_code == 2
    assert "cannot be used together" in result.output


def test_module_entrypoint() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "reaper.main", "--version"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == __version__
