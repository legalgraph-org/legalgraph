"""Hygiene of the Python code: short modules, each saying what it is for."""

import ast
from pathlib import Path

from legalgraph.hygiene.model import Finding, Rule

MAX_LINES = 300
PYTHON_DIRS = ("src", "tests")


def python_files(root: Path) -> list[Path]:
    return sorted(path for folder in PYTHON_DIRS if (root / folder).is_dir() for path in (root / folder).rglob("*.py"))


def too_long(root: Path) -> list[Finding]:
    findings = []
    for path in python_files(root):
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > MAX_LINES:
            message = f"{lines} lines; split the module (at most {MAX_LINES})"
            findings.append(Finding(path, MAX_LINES + 1, "PY001", message))
    return findings


def undocumented(root: Path) -> list[Finding]:
    """Every module under src/ opens with a docstring that says what it is for."""
    findings = []
    for path in python_files(root):
        if not path.is_relative_to(root / "src"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not ast.get_docstring(tree):
            findings.append(Finding(path, 1, "PY002", "module has no docstring saying what it is for"))
    return findings


RULES = [
    Rule("PY001", f"A Python file has at most {MAX_LINES} lines.", too_long),
    Rule("PY002", "A module under src/ starts with a docstring.", undocumented),
]
