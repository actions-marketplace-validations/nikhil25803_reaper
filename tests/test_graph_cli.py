import json

from rich.text import Text
from typer.testing import CliRunner

from reaper.main import app

runner = CliRunner()


def write_graph(project, nodes: list[dict], edges: list[dict]) -> None:
    graph_dir = project / "reaper-analysis" / "graphify-out"
    graph_dir.mkdir(parents=True, exist_ok=True)
    (graph_dir / "graph.json").write_text(
        json.dumps({"nodes": nodes, "links": edges}), encoding="utf-8"
    )


def callable_node(node_id: str, label: str, source: str, line: str) -> dict:
    return {
        "id": node_id,
        "label": label,
        "norm_label": label,
        "_origin": "ast",
        "_callable": True,
        "file_type": "code",
        "source_file": source,
        "source_location": line,
        "community": 1,
    }


def test_candidates_filter_and_sort_nodes(tmp_path) -> None:
    nodes = [
        callable_node("dead_a", "dead_a()", "src/c.py", "L20"),
        callable_node("dead_b", "dead_b()", "src/a.py", "L10"),
        callable_node("recursive", "recursive()", "src/b.py", "L5"),
        callable_node("used", "used()", "src/used.py", "L1"),
        callable_node("test_caller", "test_caller()", "tests/test_app.py", "L1"),
        callable_node("external", "external()", "src/external.py", "L1")
        | {"external": True},
        {
            "id": "data",
            "label": "data",
            "_origin": "ast",
            "file_type": "code",
            "source_file": "src/data.py",
        },
    ]
    edges = [
        {"source": "module", "target": "dead_b", "relation": "contains"},
        {"source": "recursive", "target": "recursive", "relation": "calls"},
        {"source": "dead_a", "target": "dependency", "relation": "calls"},
        {"source": "test_caller", "target": "used", "relation": "calls"},
    ]
    write_graph(tmp_path, nodes, edges)

    result = runner.invoke(app, ["graph", "candidates", str(tmp_path), "--list"])

    assert result.exit_code == 0
    assert "Review candidates only" in result.output
    assert "dead_a()" in result.output
    assert "dead_b()" in result.output
    assert "recursive()" in result.output
    assert "used()" not in result.output
    assert "test_caller()" not in result.output
    assert "external()" not in result.output
    assert result.output.index("dead_b()") < result.output.index("dead_a()")


def test_projects_lists_analyzed_paths(tmp_path, monkeypatch) -> None:
    service = tmp_path / "apps" / "user-service"
    ignored = tmp_path / "node_modules" / "dependency"
    write_graph(tmp_path, [], [])
    write_graph(service, [], [])
    write_graph(ignored, [], [])
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["graph", "projects"])

    assert result.exit_code == 0
    assert "Analyzed Projects" in result.output
    assert "user-service" in result.output
    assert "apps/user-service" in result.output
    assert "dependency" not in result.output
    assert "Found 2 analyzed project(s)" in result.output
    assert "graph candidates" in result.output


def test_projects_handles_empty_root(tmp_path) -> None:
    result = runner.invoke(app, ["graph", "projects", str(tmp_path)])

    assert result.exit_code == 0
    assert "No analyzed projects found" in result.output


def test_candidates_default_to_current_directory(tmp_path, monkeypatch) -> None:
    write_graph(
        tmp_path,
        [callable_node("local", "local()", "src/local.py", "L1")],
        [],
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["graph", "candidates", "--list"])

    assert result.exit_code == 0
    assert "local" in result.output


def test_candidates_limit_and_empty_result(tmp_path) -> None:
    nodes = [
        callable_node("first", "first()", "src/a.py", "L1"),
        callable_node("second", "second()", "src/b.py", "L1"),
    ]
    write_graph(tmp_path, nodes, [])

    summary = runner.invoke(app, ["graph", "candidates", str(tmp_path)])
    limited = runner.invoke(
        app,
        ["graph", "candidates", str(tmp_path), "--list", "--limit", "1"],
    )

    assert summary.exit_code == 0
    assert "Found 2 possible dead-code candidates" in summary.output
    assert "--list --limit 10 --page 1" in summary.output
    assert limited.exit_code == 0
    assert "first()" in limited.output
    assert "second()" not in limited.output
    assert "Page 1/2" in limited.output
    assert 'graph inspect "' in limited.output
    assert '"first"' in limited.output
    assert "--page 2" in limited.output
    warning, table_and_rest = limited.output.split("\n\n", 1)
    table, footer_and_actions = table_and_rest.split("\n\n", 1)
    footer, actions = footer_and_actions.split("\n\n", 1)
    assert "appear unused." in warning
    assert "Possible Dead-Code Candidates" in table
    assert "Page 1/2" in footer
    assert actions.startswith("Inspect:")
    assert "\nNext:" in limited.output

    write_graph(
        tmp_path,
        [callable_node("used", "used()", "src/used.py", "L1")],
        [{"source": "caller", "target": "used", "relation": "calls"}],
    )
    empty = runner.invoke(app, ["graph", "candidates", str(tmp_path)])

    assert empty.exit_code == 0
    assert "No zero-inbound callable candidates found" in empty.output


def test_candidates_paginate_all_results(tmp_path) -> None:
    nodes = [
        callable_node(
            f"node_{index:02}",
            f"node_{index:02}()",
            f"src/{index:02}.py",
            "L1",
        )
        for index in range(21)
    ]
    write_graph(tmp_path, nodes, [])

    middle = runner.invoke(
        app,
        [
            "graph",
            "candidates",
            str(tmp_path),
            "--list",
            "--limit",
            "10",
            "--page",
            "2",
        ],
    )
    final = runner.invoke(
        app,
        [
            "graph",
            "candidates",
            str(tmp_path),
            "--list",
            "--limit",
            "10",
            "--page",
            "3",
        ],
    )

    assert middle.exit_code == 0
    assert "node_10" in middle.output
    assert "node_19" in middle.output
    assert "node_09" not in middle.output
    assert "node_20" not in middle.output
    assert "Page 2/3 · Showing 11-20 of 21 candidates" in middle.output
    assert "--page 3" in middle.output
    assert final.exit_code == 0
    assert "node_20" in final.output
    assert "Page 3/3 · Showing 21-21 of 21 candidates" in final.output
    assert "Next:" not in final.output


def test_candidates_reject_invalid_pagination(tmp_path) -> None:
    write_graph(
        tmp_path,
        [callable_node("only", "only()", "src/only.py", "L1")],
        [],
    )

    out_of_range = runner.invoke(
        app,
        ["graph", "candidates", str(tmp_path), "--list", "--page", "2"],
    )
    without_list = runner.invoke(
        app, ["graph", "candidates", str(tmp_path), "--page", "2"]
    )
    invalid_limit = runner.invoke(
        app,
        ["graph", "candidates", str(tmp_path), "--list", "--limit", "101"],
    )

    assert out_of_range.exit_code == 2
    assert "valid pages are 1-1" in out_of_range.output
    assert without_list.exit_code == 2
    assert "--page requires --list" in Text.from_ansi(without_list.output).plain
    assert invalid_limit.exit_code == 2


def test_inspect_node_by_id_and_label(tmp_path) -> None:
    nodes = [
        callable_node("alpha_id", "alpha()", "src/a.py", "L2"),
        callable_node("beta_id", "beta()", "src/b.py", "L4"),
    ]
    edges = [
        {"source": "alpha_id", "target": "beta_id", "relation": "calls"},
        {"source": "external", "target": "alpha_id", "relation": "references"},
    ]
    write_graph(tmp_path, nodes, edges)

    by_id = runner.invoke(app, ["graph", "inspect", str(tmp_path), "alpha_id"])
    by_label = runner.invoke(app, ["graph", "inspect", str(tmp_path), "alpha"])

    for result in (by_id, by_label):
        assert result.exit_code == 0
        assert "Graph Node" in result.output
        assert "alpha_id" in result.output
        assert "calls" in result.output
        assert "references" in result.output
        assert "out" in result.output
        assert "in" in result.output


def test_inspect_rejects_ambiguous_or_missing_node(tmp_path) -> None:
    nodes = [
        callable_node("one", "main()", "src/one.py", "L1"),
        callable_node("two", "main()", "src/two.py", "L1"),
    ]
    write_graph(tmp_path, nodes, [])

    ambiguous = runner.invoke(app, ["graph", "inspect", str(tmp_path), "main"])
    missing = runner.invoke(app, ["graph", "inspect", str(tmp_path), "missing"])

    assert ambiguous.exit_code == 2
    assert "one" in ambiguous.output
    assert "two" in ambiguous.output
    assert missing.exit_code == 1
    assert "Node not found" in missing.output


def test_graph_command_handles_missing_and_invalid_graph(tmp_path) -> None:
    missing = runner.invoke(app, ["graph", "candidates", str(tmp_path)])
    assert missing.exit_code == 1
    assert "Run reaper --scan first" in missing.output

    graph_dir = tmp_path / "reaper-analysis" / "graphify-out"
    graph_dir.mkdir(parents=True)
    (graph_dir / "graph.json").write_text("not json", encoding="utf-8")
    invalid = runner.invoke(app, ["graph", "candidates", str(tmp_path)])

    assert invalid.exit_code == 1
    assert "Unable to read graph" in invalid.output
