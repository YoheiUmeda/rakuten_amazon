# lf — lightweight fix

Entry point for small, focused changes.
Intended to avoid the plan-mode workflow. Not a guarantee — start from a clean session.

## Prerequisites
- Start from a clean session after /clear
- Do not use when plan mode is already active or a plan file/session is in progress
- All of the following must hold:
  - ≤1 file changed, ≤10 lines diff
  - No risk to fee / pass_filter / secrets / credential handling
  - Existing tests clearly not broken

If any condition is in doubt, stop and use the normal flow.

## Steps
1. Make the edit directly. Do not create or update a plan file.
2. Run tests if applicable: `venv/Scripts/python -m pytest tests/ -q --tb=short` (doc-only: skip)
3. If the result looks correct, stage and commit (run each separately, no `&&`, no `cd`):
   ```
   git add <file>
   venv/Scripts/python -m tools.ai_orchestrator.safe_commit -m "<message>"
   ```
4. Report in exactly 3 lines:
   Changed: <file>
   Tests: pass/skip
   Commit: <hash>
