# Reaper

_Evidence-based dead-code analysis for any programming language._

[![CI](https://github.com/nikhil25803/reaper/actions/workflows/ci.yml/badge.svg)](https://github.com/nikhil25803/reaper/actions/workflows/ci.yml)
[![Test](https://github.com/nikhil25803/reaper/actions/workflows/test.yml/badge.svg)](https://github.com/nikhil25803/reaper/actions/workflows/test.yml)
[![System Prompt](https://github.com/nikhil25803/reaper/actions/workflows/system-prompt.yml/badge.svg)](https://github.com/nikhil25803/reaper/actions/workflows/system-prompt.yml)
[![Graphify](https://github.com/nikhil25803/reaper/actions/workflows/graphify.yml/badge.svg)](https://github.com/nikhil25803/reaper/actions/workflows/graphify.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/github/license/nikhil25803/reaper)](LICENSE)

## About

Dead code is difficult to identify in a real repository. A function with no obvious callers may still be a public API, framework hook, decorated handler, reflection target, or configuration-driven entry point. Asking an AI model to rediscover all of those relationships wastes context and can lead to unsafe removals.

Reaper builds a language-agnostic code graph with Graphify, ranks suspicious callables, and gives a local llama.cpp model focused source and relationship evidence. It produces reviewable reports and a reusable refactoring prompt for another AI or a human; it never edits or removes code itself.

## How it works

1. **Scan** — Graphify creates a local code graph under `reaper-analysis/`.
2. **Review** — Explore candidates manually or classify them with a local llama.cpp model.
3. **Refactor safely** — Generate a model-neutral prompt containing only evidence-backed, actionable findings.

## GitHub Actions — Recommended

The GitHub Action is the easiest way to run Reaper: it installs Reaper and Graphify, downloads the default model, performs the analysis on an Ubuntu runner, and uploads the results. You do not need to install Python, Graphify, llama.cpp, or a model on your computer.

Set up pull-request analysis in four steps:

1. Copy [the example workflow](examples/reaper-analysis.yml) to `.github/workflows/reaper-analysis.yml` in your repository.
2. In **Settings → Issues → Labels**, create a label named `reaper-analysis`.
3. Add that label to a pull request. You can also start a run manually from **Actions → Reaper Analysis → Run workflow**.
4. Open the completed workflow run and download the `reaper-analysis` artifact.

The complete default workflow is:

```yaml
name: Reaper Analysis

on:
  workflow_dispatch:
  pull_request:
    types: [labeled]

permissions:
  contents: read

jobs:
  analyze:
    if: >-
      github.event_name == 'workflow_dispatch' ||
      github.event.label.name == 'reaper-analysis'
    runs-on: ubuntu-latest
    timeout-minutes: 45

    steps:
      - name: Check out repository
        uses: actions/checkout@v7

      - name: Generate Reaper evidence and prompt
        uses: nikhil25803/reaper@v0
```

For a pull request, `actions/checkout` checks out the pull-request code and Reaper analyzes that snapshot. Reaper writes only generated files under `reaper-analysis/`; it never changes or removes project source.

The downloaded artifact contains:

| File                                  | Contents                                      |
| ------------------------------------- | --------------------------------------------- |
| `reaper-report.json`                  | Machine-readable findings and evidence.       |
| `reaper-report.md`                    | Human-readable analysis report.               |
| `refactor-prompt.md`                  | Prompt for a human or another AI model.        |
| `llama-server.log`                    | llama.cpp server output for troubleshooting.  |

The `v0` reference is updated only after a successful semantic release. The first Marketplace release containing `action.yml` must be published before this reference is available.

### Trigger analysis from an issue

GitHub uses the same labels for issues and pull requests. To let the `reaper-analysis` label trigger a run from either one, add the `issues` event to the default workflow:

```yaml
on:
  workflow_dispatch:
  pull_request:
    types: [labeled]
  issues:
    types: [labeled]
```

No other workflow changes are required: the existing job condition accepts the same label from both events. An issue does not identify a branch or commit, so an issue-triggered run analyzes the repository's default branch. The workflow file must already exist on that default branch. Results remain available from the run in the **Actions** tab; the workflow does not comment on the issue and needs no write permissions.

### Action inputs

| Input             | Default           | Purpose                                                    |
| ----------------- | ----------------- | ---------------------------------------------------------- |
| `project-path`    | `.`               | Repository directory to analyze.                           |
| `model-url`       | Qwen 0.5B Q4_K_M  | GGUF download URL used when no model path is provided.     |
| `model-path`      | Empty             | Existing GGUF file; takes precedence over `model-url`.     |
| `runtime`         | `docker`          | Use `docker` or an already installed local `llama-server`. |
| `artifact-name`   | `reaper-analysis` | Uploaded artifact name.                                    |
| `upload-artifact` | `true`            | Set to `false` when another step manages artifacts.        |

The action exposes `output-directory`, `json-report`, `markdown-report`, and `refactoring-prompt` outputs. For example, analyze a subdirectory with a custom model and artifact name:

```yaml
- id: reaper
  uses: nikhil25803/reaper@v0
  with:
    project-path: services/api
    model-url: https://example.com/custom-model.gguf
    artifact-name: api-reaper-analysis

- run: 'echo "Prompt: ${{ steps.reaper.outputs.refactoring-prompt }}"'
```

Other common adjustments are:

- **Use an existing model:** set `model-path`; it takes precedence over `model-url`.
- **Use a local llama.cpp server:** set `runtime: local` on a Linux runner where `llama-server` is already on `PATH`.
- **Manage artifacts yourself:** set `upload-artifact: "false"`, then use the action outputs in later steps.
- **Analyze another branch manually:** choose the branch in GitHub's **Run workflow** dialog. No workflow change is needed.

The Marketplace action requires Linux. Its default Docker runtime uses CPU inference and downloads the model on each run unless `model-path` is set, so large repositories can take several minutes.

## Prerequisites

| Method                  | You provide                                                                    | Reaper handles                                                    |
| ----------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| GitHub Action           | GitHub Actions enabled                                                         | Installs tools, downloads the default model, and uploads reports. |
| Docker image            | Docker                                                                         | Bundles the Reaper CLI and Graphify.                              |
| Local source with `uv`  | Python 3.11+, [uv](https://docs.astral.sh/uv/), and Graphify                   | Runs the CLI from the checkout.                                   |
| Commands on `PATH`      | Python 3.11+ and `uv`; you install Reaper and Graphify                         | Makes commands available outside the checkout.                    |
| Bash automation         | Bash, `curl`, Reaper, Graphify, a GGUF model, and free port `8080`             | Starts and stops the supplied local or Docker llama.cpp runtime.  |
| PowerShell automation   | PowerShell, Reaper, Graphify, a GGUF model, and free port `8080`               | Starts and stops the supplied local or Docker llama.cpp runtime.  |

For model-assisted local workflows, also provide either `llama-server` on `PATH` or a working Docker daemon. Local commands and scripts do not download a model or install llama.cpp. The Marketplace action does. See the [official llama.cpp installation guide](https://github.com/ggml-org/llama.cpp/blob/master/docs/install.md) for Linux, macOS, and Windows packages.

## Other ways to run Reaper

### Option 1: Docker image

Pull the published image:

```console
docker pull ghcr.io/nikhil25803/reaper:latest
```

The image becomes available after the first tagged release. Until then, build it from this repository:

```console
git clone https://github.com/nikhil25803/reaper.git
cd reaper
docker build -t reaper .
```

Check the bundled Graphify executable:

```console
docker run --rm ghcr.io/nikhil25803/reaper:latest --check graphify
```

Scan the current directory on Linux or macOS:

```console
docker run --rm \
  --user "$(id -u):$(id -g)" \
  --env HOME=/tmp \
  --volume "$PWD:/workspace" \
  ghcr.io/nikhil25803/reaper:latest --scan /workspace
```

Use this PowerShell command on Windows:

```powershell
docker run --rm --volume "${PWD}:/workspace" ghcr.io/nikhil25803/reaper:latest --scan /workspace
```

Use `reaper` instead of the GHCR image name when using a local build.

### Option 2: Local source checkout

```console
git clone https://github.com/nikhil25803/reaper.git
cd reaper
uv sync --locked
uv pip install graphifyy==0.9.95
uv run reaper --check graphify
```

Run commands through `uv run reaper`, for example:

```console
uv run reaper --scan .
```

### Option 3: Install commands on `PATH`

From a source checkout:

```console
uv tool install .
uv tool install graphifyy==0.9.95
```

If the commands are not immediately available, run `uv tool update-shell` and open a new terminal. Confirm the installation with:

```console
reaper --version
reaper --check graphify
```

### Option 4: Automated Bash or PowerShell workflow

The scripts scan and analyze the current directory, start and stop llama.cpp, and write the final refactoring prompt. They require an installed `reaper` command and a readable GGUF model.

Use a locally installed `llama-server`:

```console
./scripts/reaper-workflow.sh --runtime local --model /path/to/model.gguf
```

```powershell
.\scripts\reaper-workflow.ps1 -Runtime local -Model C:\models\model.gguf
```

Or use the official llama.cpp Docker image:

```console
docker pull ghcr.io/ggml-org/llama.cpp:server
./scripts/reaper-workflow.sh --runtime docker --model /path/to/model.gguf
```

```powershell
docker pull ghcr.io/ggml-org/llama.cpp:server
.\scripts\reaper-workflow.ps1 -Runtime docker -Model C:\models\model.gguf
```

The scripts use port `8080`, review every ranked candidate, retain llama.cpp logs under `reaper-analysis/`, and never modify source files.

## Quick start

Scan a project without an LLM:

```console
reaper --scan .
```

Count possible dead-code candidates:

```console
reaper graph candidates .
```

List the first ten candidates:

```console
reaper graph candidates . --list --limit 10 --page 1
```

Inspect one candidate using the node ID from the list:

```console
reaper graph inspect . NODE_ID
```

Candidates are leads, not proof. Public APIs, entry points, decorators, reflection, dependency injection, and framework hooks can appear unused.

## CLI reference

### Main commands

| Command                                         | Purpose                                                |
| ----------------------------------------------- | ------------------------------------------------------ |
| `reaper --help`                                 | Show command help.                                     |
| `reaper --version`                              | Show the installed version.                            |
| `reaper --check graphify`                       | Confirm Graphify is installed and print its version.   |
| `reaper --scan PATH`                            | Generate or refresh a code-only graph.                 |
| `reaper graph projects [ROOT]`                  | Find analyzed projects below a directory.              |
| `reaper graph candidates [PROJECT_PATH]`        | Count zero-inbound callable candidates.                |
| `reaper graph candidates [PROJECT_PATH] --list` | Display candidate details.                             |
| `reaper graph inspect PROJECT_PATH NODE`        | Show one node and its relationships.                   |
| `reaper analyze [PROJECT_PATH]`                 | Review ranked candidates with llama.cpp.               |
| `reaper prompt [PROJECT_PATH]`                  | Generate a refactoring prompt from an analysis report. |

### Graph options

| Option           | Applies to         | Meaning                                           |
| ---------------- | ------------------ | ------------------------------------------------- |
| `--list`         | `graph candidates` | Display candidate rows instead of only the count. |
| `--limit 1..100` | `graph candidates` | Candidates per page; default `10`.                |
| `--page N`       | `graph candidates` | One-based page number; default `1`.               |
| `--limit N`      | `graph inspect`    | Maximum relationships to display; default `50`.   |

### Analysis options

| Option                 | Meaning                                                 |
| ---------------------- | ------------------------------------------------------- |
| `--scan`               | Refresh the graph before analysis.                      |
| `--server URL`         | llama-server base URL; default `http://127.0.0.1:8080`. |
| `--model ID`           | Require a specific loaded model ID.                     |
| `--limit N`            | Review at most `N` candidates; default `20`.            |
| `--all`                | Review the complete ranked candidate pool.              |
| `--low-connectivity N` | Keep nodes with at most `N` total usage connections.    |
| `--timeout SECONDS`    | Server request timeout; default `300`.                  |

`--all` and `--limit` cannot be used together. Run any command with `--help` for its complete syntax.

## Sample responses

The following values are illustrative; your symbols and counts will differ.

### Scan

```text
 Reaper <> Graphify Scan Complete
┏━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric      ┃ Count ┃
┡━━━━━━━━━━━━━╇━━━━━━━┩
│ Nodes       │   428 │
│ Edges       │   691 │
│ Communities │    12 │
└─────────────┴───────┘
```

### Candidate count

```text
Review candidates only: entry points, public APIs, decorators, reflection,
and framework hooks can appear unused.
Found 27 possible dead-code candidates.
Next: reaper graph candidates "." --list --limit 10 --page 1
```

### Model analysis

```text
Reviewing 27 of 27 ranked callable(s) with qwen-coder...
 Reaper <> llama.cpp Analysis Complete
┏━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric       ┃ Count ┃
┡━━━━━━━━━━━━━━╇━━━━━━━┩
│ Reviewed     │    27 │
│ Likely dead  │     8 │
│ Needs review │     6 │
│ Likely used  │    13 │
└──────────────┴───────┘
JSON report: reaper-analysis/reaper-report.json
Markdown report: reaper-analysis/reaper-report.md
```

### Prompt generation

```text
Refactoring prompt: reaper-analysis/refactor-prompt.md
```

### Generated files

| File                                      | Contents                                                |
| ----------------------------------------- | ------------------------------------------------------- |
| `reaper-analysis/graphify-out/graph.json` | Graphify nodes and relationships.                       |
| `reaper-analysis/reaper-report.json`      | Versioned machine-readable findings.                    |
| `reaper-analysis/reaper-report.md`        | Human-readable findings and evidence.                   |
| `reaper-analysis/refactor-prompt.md`      | Model-neutral, evidence-based refactoring instructions. |
| `reaper-analysis/llama-server.log`        | Server output retained by the automation scripts.       |

<details>
<summary>Example: analyze a service monorepo</summary>

### Example project

```text
demo-monorepo/
├── apps/
│   ├── api-gateway/
│   ├── billing-service/
│   └── user-service/
├── packages/
│   ├── database/
│   ├── observability/
│   └── shared/
├── package.json
└── pnpm-workspace.yaml
```

### 1. Scan the root

```console
reaper --scan .
```

```text
 Reaper <> Graphify Scan Complete
┏━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric      ┃ Count ┃
┡━━━━━━━━━━━━━╇━━━━━━━┩
│ Nodes       │ 1,284 │
│ Edges       │ 2,047 │
│ Communities │    34 │
└─────────────┴───────┘
```

### 2. Discover analyzed projects

```console
reaper graph projects .
```

```text
Analyzed Projects
demo-monorepo    .
user-service    apps/user-service
billing-service apps/billing-service
Found 3 analyzed project(s).
```

### 3. List candidates

```console
reaper graph candidates . --list --limit 3 --page 1
```

```text
Possible Dead-Code Candidates
src_user_unused_legacy_handler unusedLegacyHandler() apps/user-service/src/legacy.ts L42
src_billing_old_invoice_mapper oldInvoiceMapper() apps/billing-service/src/mapper.ts L17
src_shared_stale_flag staleFlag() packages/shared/src/flags.ts L9
Page 1/9 · Showing 1-3 of 27 candidates
```

### 4. Inspect one node

```console
reaper graph inspect . src_user_unused_legacy_handler
```

```text
Graph Node
ID        src_user_unused_legacy_handler
Label     unusedLegacyHandler()
Source    apps/user-service/src/legacy.ts
Location  L42
No connections found.
```

### 5. Analyze and generate the prompt

```console
reaper analyze . --all
reaper prompt .
```

```text
Reviewing 27 of 27 ranked callable(s) with qwen-coder...
JSON report: reaper-analysis/reaper-report.json
Markdown report: reaper-analysis/reaper-report.md
Refactoring prompt: reaper-analysis/refactor-prompt.md
```

</details>

## Development

```console
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build
```

The `System Prompt` workflow runs the deterministic end-to-end scripts on Linux, macOS, and Windows. The label-gated `Llama` workflow runs the real Qwen integration on Linux when manually dispatched or when a pull request receives the `llama-analysis` label.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, quality checks, issue guidance, and the pull-request checklist.

## License

Reaper is available under the [MIT License](LICENSE).
