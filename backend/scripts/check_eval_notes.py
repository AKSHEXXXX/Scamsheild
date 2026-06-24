"""
Check that PRs touching core detection paths include an eval note.

Usage (CI):
    python scripts/check_eval_notes.py --pr-number 123
    python scripts/check_eval_notes.py --changed-files app/ml/foobar.py
"""
import os, sys, argparse, re
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent.parent / "docs" / "eval_notes"
WATCH_PATHS = [
    re.compile(r"^app/ml/"),
    re.compile(r"^routers/"),
    re.compile(r"^jobs/"),
    re.compile(r"^agents/"),
    re.compile(r"^app/data_intel/dashboard_queries\.py$"),
    re.compile(r"^app/data_intel/mongo_ops\.py$"),
]


def _touches_watched(changed_files: list[str]) -> list[str]:
    matched = []
    for f in changed_files:
        for pat in WATCH_PATHS:
            if pat.search(f):
                matched.append(f)
                break
    return matched


def _eval_note_path(pr_number: str) -> Path:
    return EVAL_DIR / f"pr_{pr_number}.md"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-number", default=os.getenv("PR_NUMBER", ""), help="PR number from CI")
    parser.add_argument("--changed-files", nargs="*", help="List of changed file paths")
    args = parser.parse_args()

    pr_number = args.pr_number
    changed = args.changed_files or []

    # If no files given, try to read from git diff
    if not changed:
        import subprocess
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main..."],
            capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent
        )
        if result.returncode == 0:
            changed = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

    if not changed:
        print("No changed files detected -- skipping eval note check.")
        sys.exit(0)

    touched = _touches_watched(changed)
    if not touched:
        print(f"No watched paths touched. Files changed: {changed}")
        sys.exit(0)

    print(f"Touched watched paths: {touched}")

    if not pr_number:
        print("WARNING: PR number not provided. Skipping eval note check.")
        sys.exit(0)

    note_path = _eval_note_path(pr_number)
    if note_path.exists():
        content = note_path.read_text().strip()
        if len(content) < 20:
            print(f"FAIL: Eval note {note_path} exists but appears empty or too short.")
            sys.exit(1)
        print(f"PASS: Eval note found at {note_path}")
        sys.exit(0)
    else:
        print(f"FAIL: No eval note found at {note_path}")
        print(f"Create it with: mkdir -p {EVAL_DIR} && echo '# PR {pr_number}' > {note_path}")
        print(f"The note must describe expected metric changes (FN/FP, pass rate, etc.).")
        sys.exit(1)


if __name__ == "__main__":
    main()
