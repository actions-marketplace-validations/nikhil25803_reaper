#!/usr/bin/env python3
"""Validate artifacts produced by a cross-platform workflow-script run."""

import json
import socket
import sys
from pathlib import Path


def main() -> None:
    project = Path(sys.argv[1]).resolve()
    output = project / "reaper-analysis"
    graph = json.loads(
        (output / "graphify-out" / "graph.json").read_text(encoding="utf-8")
    )
    report = json.loads((output / "reaper-report.json").read_text(encoding="utf-8"))
    markdown = (output / "reaper-report.md").read_text(encoding="utf-8")
    prompt = (output / "refactor-prompt.md").read_text(encoding="utf-8")

    assert graph["nodes"]
    assert isinstance(graph.get("links"), list)
    assert report["schema_version"] == 1
    assert report["model"] == "fake-workflow-model"
    assert report["findings"]
    assert markdown.strip()
    assert "# Reaper evidence-based refactoring prompt" in prompt

    actionable = [
        item
        for item in report["findings"]
        if item["verdict"] in {"likely_dead", "needs_review"}
    ]
    likely_used = [
        item for item in report["findings"] if item["verdict"] == "likely_used"
    ]
    assert actionable
    assert likely_used
    assert all(item["symbol"] in prompt for item in actionable)
    assert all(item["symbol"] not in prompt for item in likely_used)

    with socket.socket() as client:
        client.settimeout(1)
        assert client.connect_ex(("127.0.0.1", 8080)) != 0


if __name__ == "__main__":
    main()
