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
apply_surgical_fix  →  writes corrected code
        ↓
verify_fix  →  "ALL TESTS PASSED"
        ↓
create_git_branch / commit_fix  →  ships it
```

The entire loop runs in seconds, locally, with no code leaving your machine.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `check_pipeline_status()` | Run pytest, report PASSED/FAILED with failure details |
| `list_files()` | List all Python files in the target app |
| `read_code_file(filename)` | Read a file with line numbers |
| `apply_surgical_fix(filename, new_content)` | Overwrite a file with fixed code |
| `verify_fix()` | Re-run pytest to confirm the fix |
| `create_git_branch(branch_name)` | Create and switch to a new git branch |
| `commit_fix(message)` | Stage and commit changes |
| `reset_broken_app()` | Reset to buggy state for repeatable demos |

## Setup

**Prerequisites**: Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/hl9082/healcontrol.git
cd healcontrol
uv sync
```

Optional — copy `.env.example` to `.env` and fill in IBM watsonx.ai credentials:

```bash
cp .env.example .env
```

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
├── src/server.py          ← MCP server (8 tools)
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
- **Intelligence**: IBM Bob + custom system prompts
- **Integration**: Local `subprocess` management for Git and Pytest execution
- **Transport**: stdio (works with any MCP client)

## What's Next

- `analyze_with_watsonx()` tool — send error output to IBM Granite for analysis
- "Push to Cloud" tool that automatically opens a PR once local tests pass
- Support for multiple target apps beyond the demo
