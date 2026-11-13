"""Project hygiene: conventions of this repository that ruff and SHACL cannot check.

Each rule has a code (PY… for Python, ONT… for the ontology's files), a one-line summary and a check
that returns findings. `legalgraph hygiene` runs them all and fails on any finding; `make check`
runs it. Add a rule by writing its check in the matching module and listing it in that module's RULES.
"""

from pathlib import Path

from legalgraph.hygiene import ontology, python
from legalgraph.hygiene.model import Finding, Rule

RULES: list[Rule] = [*python.RULES, *ontology.RULES]


def check(root: Path, codes: set[str] | None = None) -> list[Finding]:
    """The findings of every rule (or of the given codes) under the repository root."""
    rules = [rule for rule in RULES if codes is None or rule.code in codes]
    return sorted(finding for rule in rules for finding in rule(root))


__all__ = ["RULES", "Finding", "Rule", "check"]
