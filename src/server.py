"""
HealControl — Local-First DevOps MCP Server.

Team: Healing Control
Main Author: Olivier Couthaud
Co-Authors: Huy Le, Vaibhav, Sachi Kiny

Description:
    An MCP (Model Context Protocol) server that gives AI assistants the ability
    to autonomously detect test failures, read broken source code, apply surgical
    fixes, verify corrections, and ship changes via Git — all locally.

    Tools provided:
        - check_pipeline_status  : Run the test suite and report pass/fail.
        - list_files             : List Python files in the active app.
        - read_code_file         : Read a source file with line numbers.
        - apply_surgical_fix     : Overwrite a file with corrected code.
        - verify_fix             : Re-run tests to confirm the fix.
        - create_git_branch      : Create and switch to a new branch.
        - commit_fix             : Stage and commit changes.
        - reset_broken_app       : Reset the demo app to its buggy state.
        - analyze_with_watsonx   : AI-powered diagnosis via IBM Granite.
        - push_to_cloud          : Push a branch and open a GitHub PR.
        - list_apps              : List all registered target apps.
        - set_active_app         : Switch the active target app.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# watsonx config
_watsonx_token: str | None = None


def _get_watsonx_token() -> str | None:
    """Get an IAM bearer token for watsonx. Cached for the process lifetime."""
    global _watsonx_token
    if _watsonx_token is not None:
        return _watsonx_token

    api_key = os.getenv("WATSONX_APIKEY")
    if not api_key:
        return None

    resp = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        data={"apikey": api_key, "grant_type": "urn:ibm:params:oauth:grant-type:apikey"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    _watsonx_token = resp.json()["access_token"]
    return _watsonx_token


mcp = FastMCP("healcontrol")

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# ── Multi-app config ─────────────────────────────────────────────────

_app_config: dict = {}
_active_app: str = ""

# Original buggy source (for reset of demo app)
BUGGY_MAIN = """\
def calculate_discount(price, discount_percent):
    # BUG: subtracts decimal instead of multiplying
    return price - discount_percent
"""


def _load_config() -> None:
    """Load healcontrol.json from PROJECT_ROOT, or fall back to defaults."""
    global _app_config, _active_app

    config_path = PROJECT_ROOT / "healcontrol.json"
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: failed to parse healcontrol.json: {e}", file=sys.stderr)
            data = {}
        _app_config = data.get("apps", {})
        if not _app_config:
            # Fall back to defaults if apps dict is empty or missing
            _app_config = {
                "broken_app": {
                    "path": "broken_app",
                    "test_command": "pytest",
                    "description": "Demo app with discount calculation bug",
                }
            }
        _active_app = data.get("default_app", "")
        # If default_app not in apps, pick the first one
        if _active_app not in _app_config and _app_config:
            _active_app = next(iter(_app_config))
    else:
        # Fallback: hardcoded broken_app behavior
        _app_config = {
            "broken_app": {
                "path": "broken_app",
                "test_command": "pytest",
                "description": "Demo app with discount calculation bug",
            }
        }
        _active_app = "broken_app"


_load_config()


def _get_active_app_config() -> dict:
    """Return the config dict for the active app."""
    return _app_config.get(_active_app, {})


def _get_target_dir() -> Path:
    """Return the resolved path of the active app's directory."""
    cfg = _get_active_app_config()
    rel_path = cfg.get("path", _active_app)
    return (PROJECT_ROOT / rel_path).resolve()


def _get_test_command() -> str:
    """Return the test command for the active app."""
    cfg = _get_active_app_config()
    return cfg.get("test_command", "pytest")


# ── Helpers ───────────────────────────────────────────────────────────

def _safe_path(filename: str) -> Path:
    """Resolve *filename* inside the active app dir; reject traversal attempts."""
    target = _get_target_dir()
    resolved = (target / filename).resolve()
    if not resolved.is_relative_to(target):
        raise ValueError(f"Path traversal blocked: {filename}")
    return resolved


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a subprocess with sane defaults."""
    if cwd is None:
        cwd = _get_target_dir()
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        stdin=subprocess.DEVNULL,
    )


def _extract_failures(output: str) -> str:
    """Return only the FAILURES section of pytest output, if present."""
    marker = "FAILURES"
    idx = output.find(marker)
    if idx == -1:
        return output
    return output[idx:]


def _build_test_cmd() -> list[str]:
    """Build the test command list for the active app."""
    test_cmd = _get_test_command()
    target = _get_target_dir()
    if test_cmd == "pytest":
        return [sys.executable, "-m", "pytest", str(target), "-v", "--tb=short"]
    # For custom test commands, split and return as-is
    return test_cmd.split()


# ── MCP Tools ─────────────────────────────────────────────────────────

# ── Multi-app management ──

@mcp.tool()
def list_apps() -> str:
    """List all registered apps and their descriptions."""
    if not _app_config:
        return "No apps configured. Add a healcontrol.json to the project root."
    lines = []
    for name, cfg in _app_config.items():
        marker = " (active)" if name == _active_app else ""
        desc = cfg.get("description", "No description")
        lines.append(f"  {name}{marker} — {desc}")
    return "Registered apps:\n" + "\n".join(lines)


@mcp.tool()
def set_active_app(app_name: str) -> str:
    """Switch the active target app by name."""
    global _active_app
    if app_name not in _app_config:
        available = ", ".join(_app_config.keys())
        return f"Unknown app: {app_name}. Available: {available}"
    _active_app = app_name
    target = _get_target_dir()
    if not target.exists():
        return f"Warning: switched to '{app_name}' but directory {target} does not exist."
    return f"Active app set to: {app_name} ({target})"


# ── Pipeline / file tools ──

@mcp.tool()
def check_pipeline_status() -> str:
    """Run the test suite and report PASSED or FAILED with details."""
    result = _run(_build_test_cmd(), cwd=PROJECT_ROOT)
    combined = result.stdout + result.stderr
    status = "PASSED" if result.returncode == 0 else "FAILED"
    details = _extract_failures(combined) if status == "FAILED" else combined
    return f"Pipeline status: {status}\n\n{details}"


@mcp.tool()
def list_files() -> str:
    """List all Python files in the active app directory."""
    target = _get_target_dir()
    files = sorted(target.glob("*.py"))
    return "\n".join(f.name for f in files)


@mcp.tool()
def read_code_file(filename: str) -> str:
    """Read a file from the active app with line numbers prepended."""
    path = _safe_path(filename)
    if not path.exists():
        return f"File not found: {filename}"
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered)


@mcp.tool()
def apply_surgical_fix(filename: str, new_content: str) -> str:
    """Overwrite a file in the active app with fixed code."""
    path = _safe_path(filename)
    path.write_text(new_content, encoding="utf-8")
    return f"File written: {filename} ({len(new_content)} bytes)"


@mcp.tool()
def verify_fix() -> str:
    """Re-run the test suite to confirm the fix works."""
    result = _run(_build_test_cmd(), cwd=PROJECT_ROOT)
    combined = result.stdout + result.stderr
    if result.returncode == 0:
        return f"ALL TESTS PASSED\n\n{combined}"
    return f"TESTS STILL FAILING\n\n{combined}"


@mcp.tool()
def create_git_branch(branch_name: str) -> str:
    """Create and switch to a new git branch in the active app."""
    result = _run(["git", "checkout", "-b", branch_name])
    if result.returncode != 0:
        return f"Error creating branch: {result.stderr}"
    return f"Branch created and checked out: {branch_name}"


@mcp.tool()
def commit_fix(message: str) -> str:
    """Stage all changes and commit in the active app."""
    add = _run(["git", "add", "."])
    if add.returncode != 0:
        return f"Error staging files: {add.stderr}"
    commit = _run(["git", "commit", "-m", message])
    if commit.returncode != 0:
        return f"Error committing: {commit.stderr}"
    return f"Committed: {message}\n{commit.stdout}"


@mcp.tool()
def reset_broken_app() -> str:
    """Reset main.py to the original buggy state for repeatable demos."""
    if _active_app != "broken_app":
        return (
            f"Reset is only available for the demo app 'broken_app'. "
            f"Current active app is '{_active_app}'."
        )
    target = _get_target_dir()
    path = target / "main.py"
    path.write_text(BUGGY_MAIN, encoding="utf-8")
    return "broken_app/main.py reset to buggy state."


# ── AI analysis ──

@mcp.tool()
def analyze_with_watsonx(error_output: str, filename: str = "") -> str:
    """Send test failure output to IBM Granite for AI-powered diagnosis."""
    url = os.getenv("WATSONX_URL")
    project_id = os.getenv("WATSONX_PROJECT_ID")

    if not all([url, project_id]):
        return (
            "watsonx.ai not configured. "
            "Set WATSONX_APIKEY, WATSONX_URL, and WATSONX_PROJECT_ID in .env"
        )

    token = _get_watsonx_token()
    if token is None:
        return "watsonx.ai not configured. Set WATSONX_APIKEY in .env"

    file_context = f" from file '{filename}'" if filename else ""

    prompt = (
        "You are a Python debugging expert. Analyze the following pytest failure "
        f"output{file_context}. "
        "Provide your analysis in this structured format:\n\n"
        "ROOT CAUSE: <one-line summary of the bug>\n"
        "FIX SUGGESTION: <minimal code change needed>\n"
        "CONFIDENCE: <high|medium|low>\n"
        "EXPLANATION: <brief explanation of why this fix works>\n\n"
        f"```\n{error_output}\n```\n\n"
        "Analysis:"
    )

    try:
        resp = requests.post(
            f"{url}/ml/v1/text/chat?version=2024-10-25",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "model_id": "ibm/granite-4-h-small",
                "project_id": project_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.2,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"watsonx.ai analysis failed: {e}"


# ── Push to cloud ──

@mcp.tool()
def push_to_cloud(branch_name: str, title: str, body: str = "") -> str:
    """Push the current branch and open a GitHub PR (requires gh CLI)."""
    # Check that gh is available
    if not shutil.which("gh"):
        return "Error: GitHub CLI (gh) is not installed or not on PATH."

    # Use the active app's directory for git operations (matches create_git_branch/commit_fix)
    target = _get_target_dir()

    # Verify gh is authenticated
    auth_check = _run(["gh", "auth", "status"], cwd=target)
    if auth_check.returncode != 0:
        return (
            "Error: gh CLI is not authenticated. "
            "Run 'gh auth login' or set the GITHUB_TOKEN env var.\n"
            + auth_check.stderr
        )

    # Run tests first — refuse to push if they fail
    test_result = _run(_build_test_cmd(), cwd=PROJECT_ROOT)
    if test_result.returncode != 0:
        return (
            "Refusing to push: tests are failing. Fix the tests first.\n\n"
            + _extract_failures(test_result.stdout + test_result.stderr)
        )

    # Push the branch
    push = _run(["git", "push", "-u", "origin", branch_name], cwd=target)
    if push.returncode != 0:
        return f"Error pushing branch: {push.stderr}"

    # Create the PR
    pr_cmd = [
        "gh", "pr", "create",
        "--base", "main",
        "--head", branch_name,
        "--title", title,
    ]
    if body:
        pr_cmd.extend(["--body", body])
    else:
        pr_cmd.extend(["--body", "Automated fix via HealControl"])

    pr_result = _run(pr_cmd, cwd=target)
    if pr_result.returncode != 0:
        return f"Error creating PR: {pr_result.stderr}"

    pr_url = pr_result.stdout.strip()
    return f"PR created successfully: {pr_url}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
