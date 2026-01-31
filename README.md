# Healing-Control

Local-First DevOps Agent that detects test failures, reads broken code, applies fixes, and verifies — all via MCP tools.

Built for the IBM Hackathon.

## How It Works

Healing-Control is an MCP server that gives any AI assistant (IBM Bob, Claude Desktop, or any MCP client) the ability to autonomously fix broken code:

```
check_pipeline_status  →  "3 tests FAILED"
        ↓
list_files / read_code_file  →  finds the bug
        ↓
analyze_with_watsonx  →  AI-powered root cause analysis
        ↓
apply_surgical_fix  →  writes corrected code
        ↓
verify_fix  →  "ALL TESTS PASSED"
        ↓
create_git_branch / commit_fix  →  ships it
        ↓
push_to_cloud  →  opens a GitHub PR
```

The entire loop runs locally, with no code leaving your machine (except the PR push).

## MCP Tools

### Pipeline & File Tools

| Tool | Purpose |
|------|---------|
| `check_pipeline_status()` | Run tests, report PASSED/FAILED with failure details |
| `list_files()` | List all Python files in the active app |
| `read_code_file(filename)` | Read a file with line numbers |
| `apply_surgical_fix(filename, new_content)` | Overwrite a file with fixed code |
| `verify_fix()` | Re-run tests to confirm the fix |
| `create_git_branch(branch_name)` | Create and switch to a new git branch |
| `commit_fix(message)` | Stage and commit changes |
| `reset_broken_app()` | Reset demo app to buggy state (broken_app only) |

### AI Analysis

| Tool | Purpose |
|------|---------|
| `analyze_with_watsonx(error_output, filename?)` | Send error output to IBM Granite for structured diagnosis (root cause, fix suggestion, confidence) |

### Multi-App Management

| Tool | Purpose |
|------|---------|
| `list_apps()` | List all registered apps and their descriptions |
| `set_active_app(app_name)` | Switch the active target app |

### Push to Cloud

| Tool | Purpose |
|------|---------|
| `push_to_cloud(branch_name, title, body?)` | Run tests, push branch, and open a GitHub PR |

## Multi-App Configuration

HealControl supports multiple target apps via `healcontrol.json` in the project root:

```json
{
  "apps": {
    "broken_app": {
      "path": "broken_app",
      "test_command": "pytest",
      "description": "Demo app with discount calculation bug"
    },
    "my_service": {
      "path": "services/my_service",
      "test_command": "pytest",
      "description": "Production microservice"
    }
  },
  "default_app": "broken_app"
}
```

Each app entry has:
- `path` — relative path from project root to the app directory
- `test_command` — command used to run tests (defaults to `pytest`)
- `description` — human-readable description shown in `list_apps()`

If `healcontrol.json` is missing, the server falls back to the built-in `broken_app` configuration.

## Setup

**Prerequisites**: Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/hl9082/healcontrol.git
cd healcontrol
uv sync
```

Optional — copy `.env.example` to `.env` and fill in credentials:

```bash
cp .env.example .env
```

Environment variables:
- `WATSONX_APIKEY`, `WATSONX_URL`, `WATSONX_PROJECT_ID` — for AI-powered analysis via IBM Granite
- `GITHUB_TOKEN` — for `push_to_cloud()` (alternatively, authenticate with `gh auth login`)

## Running the Server

**With MCP Inspector** (for testing):

```bash
uv run mcp dev src/server.py
```

**With VS Code** (Copilot/Bob): Open the project — `.vscode/mcp.json` is already configured.

**Stdio transport** (for any MCP client):

```bash
uv run python src/server.py
```

## Demo

The `broken_app/` directory contains a buggy `calculate_discount` function and 3 failing tests. The AI agent uses the MCP tools to find and fix the bug autonomously.

Run the tests yourself to see the failures:

```bash
uv run pytest broken_app/ -v
```

After the agent fixes it, `reset_broken_app()` restores the buggy state so you can demo again.

## Architecture

```
healcontrol/
├── src/server.py          ← MCP server (13 tools)
├── healcontrol.json       ← Multi-app registry config
├── broken_app/            ← Demo app with intentional bug
│   ├── main.py            ← Buggy discount calculation
│   └── test_main.py       ← 3 tests that define correct behavior
├── prompts/
│   └── system_prompt.txt  ← AI agent instructions
├── .vscode/mcp.json       ← VS Code MCP config
├── pyproject.toml
└── .env.example
```

## How We Built It

- **Backend**: Python `FastMCP` server as the bridge between AI and local dev tools
- **Intelligence**: IBM Bob + IBM Granite (via watsonx.ai) + custom system prompts
- **Integration**: Local `subprocess` management for Git, Pytest, and GitHub CLI
- **Transport**: stdio (works with any MCP client)
