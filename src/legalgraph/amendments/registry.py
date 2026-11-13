"""The registry: which acts the live check covers, and why not.

The committed registry is data/amendment-checks/coverage.yaml, one line per lgo:LegalAct: covered
acts carry `kind` (a checker) and `arg` (the portal identifier), exempt acts carry `exempt` with the
reason. Every act in the graph must be registered (tested).
"""

import functools
from collections.abc import Callable
from pathlib import Path

import yaml

from legalgraph.amendments.eu import check_cellar
from legalgraph.amendments.europe import (
    check_boe,
    check_fedlex,
    check_gesetze,
    check_isap,
    check_legislation_mt,
    check_lovdata,
    check_normattiva,
    check_pgdl,
    check_riksdagen,
    check_ris,
    check_wetten,
)
from legalgraph.amendments.model import LiveAmendment
from legalgraph.amendments.world import (
    check_cppa,
    check_ecfr,
    check_laws_lois,
    check_legislation_gov,
    check_mevzuat,
    check_uscode,
)
from legalgraph.load import DEFAULT_DATA_DIR

REGISTRY = DEFAULT_DATA_DIR / "amendment-checks" / "coverage.yaml"


def checker_kinds() -> dict[str, Callable[[str], LiveAmendment]]:
    """kind -> fetcher function, keyed as coverage.yaml uses them."""
    return {
        "gesetze": check_gesetze,
        "cellar": check_cellar,
        "legislation": check_legislation_gov,
        "ris": check_ris,
        "laws_lois": check_laws_lois,
        "fedlex": check_fedlex,
        "normattiva": check_normattiva,
        "boe": check_boe,
        "pgdl": check_pgdl,
        "legislation_mt": check_legislation_mt,
        "lovdata": check_lovdata,
        "riksdagen": check_riksdagen,
        "wetten": check_wetten,
        "ecfr": lambda arg: check_ecfr(*arg.split(":")),
        "uscode": lambda arg: check_uscode(*arg.split(":")),
        "cppa": check_cppa,
        "mevzuat": check_mevzuat,
        "isap": check_isap,
    }


def load_registry(path: Path = REGISTRY) -> dict[str, dict]:
    """The coverage registry: act id -> {kind, arg} or {exempt}."""
    return yaml.safe_load(path.read_text())


@functools.cache
def registry() -> dict[str, dict]:
    """The committed coverage registry, loaded once."""
    return load_registry()


def live_checks(entries: dict[str, dict]) -> dict[str, tuple[str, str]]:
    """act id -> (arg, kind) for every covered entry."""
    return {act: (e["arg"], e["kind"]) for act, e in entries.items() if "kind" in e}


def exempt_acts(entries: dict[str, dict]) -> dict[str, str]:
    """act id -> exemption reason."""
    return {act: e["exempt"] for act, e in entries.items() if "exempt" in e}


def fetch_live(act: str) -> LiveAmendment | None:
    """The latest amendment the official portal shows for `act`, or None when no checker exists."""
    entry = live_checks(registry()).get(act)
    if entry is None:
        return None
    arg, kind = entry
    return checker_kinds()[kind](arg)
