"""What a hygiene rule is and what it reports."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, order=True)
class Finding:
    path: Path
    line: int
    code: str
    message: str

    def show(self, root: Path) -> str:
        where = self.path.relative_to(root) if self.path.is_relative_to(root) else self.path
        return f"{where}:{self.line}: {self.code} {self.message}"


@dataclass(frozen=True)
class Rule:
    """One project convention: a code, what it asks for, and the check that finds breaches of it under
    the repository root."""

    code: str
    summary: str
    check: Callable[[Path], list[Finding]]

    def __call__(self, root: Path) -> list[Finding]:
        return self.check(root)


def line_of(path: Path, text: str) -> int:
    """The first line of the file that contains the text, or 1."""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if text in line:
            return number
    return 1
