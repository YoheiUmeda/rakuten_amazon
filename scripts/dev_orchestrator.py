# scripts/dev_orchestrator.py
"""
MVP dev orchestrator.

Usage:
    python scripts/dev_orchestrator.py --task orchestrator_tasks/example_task.json --mode dry-run
    python scripts/dev_orchestrator.py --task orchestrator_tasks/example_task.json --mode commit
    python scripts/dev_orchestrator.py --task orchestrator_tasks/example_task.json --mode push

Modes:
    dry-run  Show git status/diff and run pytest. No git write operations.
    commit   Run pytest, then add/commit target files only (no push).
    push     Run pytest + check dirty files, then add/commit/push if all clear.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return run(["git"] + args, cwd=cwd)


def load_task(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def show_status(repo: Path) -> None:
    r = git(["status", "--short"], repo)
    print("=== git status --short ===")
    print(r.stdout or "(clean)")


def get_dirty_files(repo: Path) -> list[str]:
    """
    Return all dirty file paths via git status --porcelain -uall.
    -uall expands untracked directories to individual files.
    Paths are normalised to forward-slash relative paths.
    Covers: modified (staged/unstaged) and untracked files.
    """
    r = git(["status", "--porcelain", "-uall"], repo)
    names: list[str] = []
    for line in r.stdout.splitlines():
        if not line:
            continue
        parts = line[3:].strip()
        # handle rename: "old -> new"
        path = parts.split(" -> ")[-1]
        # normalise to forward-slash (git always outputs forward-slash, but be safe)
        names.append(path.replace("\\", "/"))
    return names


def show_dirty(repo: Path) -> list[str]:
    names = get_dirty_files(repo)
    print("=== dirty files (status --porcelain) ===")
    for n in names:
        print(" ", n)
    if not names:
        print("  (none)")
    return names


def check_dirty_outside_targets(dirty: list[str], targets: list[str]) -> list[str]:
    """Return files that are dirty but NOT in targets.
    Both sides are normalised to forward-slash for comparison.
    """
    norm_targets = {t.replace("\\", "/") for t in targets}
    return [f for f in dirty if f.replace("\\", "/") not in norm_targets]


def run_pytest(commands: list[str], repo: Path) -> bool:
    """Run each pytest command via PowerShell. Returns True if all pass."""
    all_passed = True
    for cmd in commands:
        print(f"\n=== pytest: {cmd} ===")
        r = subprocess.run(
            ["powershell.exe", "-NonInteractive", "-Command",
             f'$env:PYTHONPATH="."; {cmd}'],
            cwd=repo,
        )
        if r.returncode != 0:
            print(f"FAILED (exit {r.returncode})")
            all_passed = False
        else:
            print("PASSED")
    return all_passed


def git_add_commit(targets: list[str], message: str, repo: Path) -> bool:
    r = git(["add"] + targets, repo)
    if r.returncode != 0:
        print("git add failed:", r.stderr)
        return False

    # Check if there's anything staged
    staged = git(["diff", "--cached", "--name-only"], repo)
    if not staged.stdout.strip():
        print("Nothing to commit (targets unchanged).")
        return True

    r = git(["commit", "-m", message], repo)
    if r.returncode != 0:
        print("git commit failed:", r.stderr)
        return False
    print("Committed:", r.stdout.strip().splitlines()[0] if r.stdout else "")
    return True


def git_push(repo: Path) -> bool:
    r = git(["push"], repo)
    if r.returncode != 0:
        print("git push failed:", r.stderr)
        return False
    print("Pushed:", r.stdout.strip() or r.stderr.strip())
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Dev orchestrator MVP")
    parser.add_argument("--task", required=True, help="Path to task JSON")
    parser.add_argument(
        "--mode",
        choices=["dry-run", "commit", "push"],
        default="dry-run",
        help="Execution mode",
    )
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent.parent
    task_path = Path(args.task)
    if not task_path.is_absolute():
        task_path = repo / task_path

    task = load_task(task_path)
    goal = task.get("goal", "(no goal)")
    targets: list[str] = task.get("targets", [])
    pytest_commands: list[str] = task.get("pytest_commands", [])
    commit_message: str = task.get("commit_message", "chore: update")
    allow_push: bool = task.get("allow_push", False)

    print(f"\n{'='*50}")
    print(f"Goal   : {goal}")
    print(f"Mode   : {args.mode}")
    print(f"Targets: {targets}")
    print(f"{'='*50}\n")

    # 1. Show status + dirty files
    show_status(repo)
    dirty = show_dirty(repo)

    # 2. dry-run: pytest only, no git writes
    if args.mode == "dry-run":
        if pytest_commands:
            run_pytest(pytest_commands, repo)
        else:
            print("\n(no pytest_commands defined)")
        print("\n[dry-run] No git operations performed.")
        return

    # 3. commit / push: run pytest first
    if pytest_commands:
        passed = run_pytest(pytest_commands, repo)
        if not passed:
            print("\nAborting: pytest failed.")
            sys.exit(1)
    else:
        print("\n(no pytest_commands - skipping pytest)")

    # 4. commit mode
    if args.mode == "commit":
        ok = git_add_commit(targets, commit_message, repo)
        if not ok:
            sys.exit(1)
        return

    # 5. push mode
    if args.mode == "push":
        if not allow_push:
            print("allow_push=false in task JSON. Aborting push.")
            sys.exit(1)

        outside = check_dirty_outside_targets(dirty, targets)
        if outside:
            print("\nAborting push: dirty files outside targets:")
            for f in outside:
                print(" ", f)
            sys.exit(1)

        ok = git_add_commit(targets, commit_message, repo)
        if not ok:
            sys.exit(1)

        ok = git_push(repo)
        if not ok:
            sys.exit(1)


if __name__ == "__main__":
    main()
