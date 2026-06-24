"""Generate Obsidian-compatible code graph markdown files.

Usage:
    python scripts/generate_code_graph.py

Output:
    docs/obsidian/*.md — one note per module with [[wikilinks]] to dependencies
"""

import ast
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OBSIDIAN_DIR = BASE / "docs" / "obsidian"
OBSIDIAN_DIR.mkdir(parents=True, exist_ok=True)

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", "artifacts", "node_modules"}
SKIP_FILES = {"__init__.py", "conftest.py"}
INTERESTING_DIRS = {"routers", "app", "agents", "schemas", "scripts"}

def extract_imports(filepath: Path) -> list[str]:
    with open(filepath) as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError:
            return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                full = f"{mod}.{alias.name}" if mod else alias.name
                imports.append(full)
    return imports

def is_local(imp: str) -> bool:
    parts = imp.split(".")
    return parts[0] in ("app", "routers", "agents", "schemas", "scripts", "utils")

def module_name(filepath: Path) -> str:
    rel = filepath.relative_to(BASE)
    stem = rel.stem
    parent = rel.parent
    if str(parent) == ".":
        return stem
    return f"{parent}/{stem}"

def generate_note(filepath: Path):
    mod = module_name(filepath)
    imports = extract_imports(filepath)
    local_imports = sorted(set(i for i in imports if is_local(i)))
    imported_by = sorted(set(i for i in imports if is_local(i)))

    lines = [f"# {mod}", ""]
    if local_imports:
        lines.append("## Imports")
        lines.append("")
        for i in local_imports:
            wiki = i.replace(".", "/")
            lines.append(f"- [[{wiki}]]")
        lines.append("")

    backlinks = _find_backlinks(filepath)
    if backlinks:
        lines.append("## Imported By")
        lines.append("")
        for b in backlinks:
            lines.append(f"- [[{b}]]")
        lines.append("")

    out = OBSIDIAN_DIR / f"{mod}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))

_backlink_cache = {}

def _find_backlinks(filepath: Path) -> list[str]:
    rel = filepath.relative_to(BASE)
    mod = module_name(filepath)
    if mod not in _backlink_cache:
        backlinks = set()
        for py in BASE.rglob("*.py"):
            if any(s in str(py) for s in SKIP_DIRS):
                continue
            if py.name in SKIP_FILES:
                continue
            if py == filepath:
                continue
            imports = extract_imports(py)
            for imp in imports:
                if is_local(imp) and mod in imp.replace("/", "."):
                    backlinks.add(module_name(py))
        _backlink_cache[mod] = sorted(backlinks)
    return _backlink_cache[mod]

def main():
    for py in BASE.rglob("*.py"):
        if any(s in str(py) for s in SKIP_DIRS):
            continue
        if py.name in SKIP_FILES:
            continue
        parts = py.relative_to(BASE).parts
        if not any(p in INTERESTING_DIRS for p in parts):
            if py.parent != BASE or py.name == "generate_code_graph.py":
                continue
        generate_note(py)
    print(f"Generated {len(list(OBSIDIAN_DIR.rglob('*.md')))} notes in {OBSIDIAN_DIR}")

if __name__ == "__main__":
    main()
