"""HealControl — Local-First DevOps MCP Server."""

import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("healcontrol")

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
TARGET_DIR = PROJECT_ROOT / "broken_app"

# ── Original buggy source (for reset) ────────────────────────────────
BUGGY_MAIN = """\
def calculate_discount(price, discount_percent):
    # BUG: subtracts decimal instead of multiplying
    return price - discount_percent
"""


# ── Helpers ───────────────────────────────────────────────────────────

def _safe_path(filename: str) -> Path:
    """Resolve *filename* inside TARGET_DIR; reject traversal attempts."""
    resolved = (TARGET_DIR / filename).resolve()
    if not str(resolved).startswith(str(TARGET_DIR)):
        raise ValueError(f"Path traversal blocked: {filename}")
    return resolved


def _run(cmd: list[str], cwd: Path = TARGET_DIR) -> subprocess.CompletedProcess:
    """Run a subprocess with sane defaults."""
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


# ── MCP Tools ─────────────────────────────────────────────────────────

@mcp.tool()
def check_pipeline_status() -> str:
    """Run the test suite and report PASSED or FAILED with details."""
    result = _run(
        [sys.executable, "-m", "pytest", str(TARGET_DIR), "-v", "--tb=short"],
        cwd=PROJECT_ROOT,
    )
    combined = result.stdout + result.stderr
    status = "PASSED" if result.returncode == 0 else "FAILED"
    details = _extract_failures(combined) if status == "FAILED" else combined
    return f"Pipeline status: {status}\n\n{details}"


@mcp.tool()
def list_files() -> str:
    """List all Python files in the broken_app directory."""
    files = sorted(TARGET_DIR.glob("*.py"))
    return "\n".join(f.name for f in files)


@mcp.tool()
def read_code_file(filename: str) -> str:
    """Read a file from broken_app with line numbers prepended."""
    path = _safe_path(filename)
    if not path.exists():
        return f"File not found: {filename}"
    lines = path.read_text(encoding="utf-8").splitlines()
    numbered = [f"{i + 1:4d} | {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered)


@mcp.tool()
def apply_surgical_fix(filename: str, new_content: str) -> str:
    """Overwrite a file in broken_app with fixed code."""
    path = _safe_path(filename)
    path.write_text(new_content, encoding="utf-8")
    return f"File written: {filename} ({len(new_content)} bytes)"


@mcp.tool()
def verify_fix() -> str:
    """Re-run the test suite to confirm the fix works."""
    result = _run(
        [sys.executable, "-m", "pytest", str(TARGET_DIR), "-v", "--tb=short"],
        cwd=PROJECT_ROOT,
    )
    combined = result.stdout + result.stderr
    if result.returncode == 0:
        return f"ALL TESTS PASSED\n\n{combined}"
    return f"TESTS STILL FAILING\n\n{combined}"


@mcp.tool()
def create_git_branch(branch_name: str) -> str:
    """Create and switch to a new git branch in broken_app."""
    result = _run(["git", "checkout", "-b", branch_name])
    if result.returncode != 0:
        return f"Error creating branch: {result.stderr}"
    return f"Branch created and checked out: {branch_name}"


@mcp.tool()
def commit_fix(message: str) -> str:
    """Stage all changes and commit in broken_app."""
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
    path = TARGET_DIR / "main.py"
    path.write_text(BUGGY_MAIN, encoding="utf-8")
    # Also switch back to main branch if it exists
    _run(["git", "checkout", "main"])
    return "broken_app/main.py reset to buggy state."


if __name__ == "__main__":
    mcp.run(transport="stdio")
