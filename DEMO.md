# Demo & Filming Instructions

## Scene 1: The "Logic Bug" (Math Error)
**Goal:** Show Bob analyzing a test failure and fixing the math logic.
1. `git checkout main`
2. Run `uv run pytest broken_app/`
3. **Result:** Tests fail (Assertion Error).
4. **Action:** Ask Bob "Fix the logic error".

## Scene 2: The "Crash" (Syntax Error)
**Goal:** Show Bob fixing a file that wont even run.
1. `git checkout feature/syntax-error`
2. Run `uv run pytest broken_app/`
3. **Result:** Immediate crash (SyntaxError: invalid syntax).
4. **Action:** Ask Bob "Fix the syntax error".

## Emergency Mode (If Internet Fails)
If GitHub is down, the system will use `src/mock_data.py` to simulate the logs.

