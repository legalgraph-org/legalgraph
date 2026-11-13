"""Live amendment checks: does the official portal still show the amendment the graph recorded?

Each registered checker fetches the act's official page, extracts the latest amendment the portal
knows, and `compare()` contrasts it with the `lgo:AmendmentCheck` data under
`data/amendment-checks/`. Portals that cannot be read programmatically (JavaScript-only, blocked,
no version metadata) have no checker: their acts are skipped rather than faked.

Usage:
    legalgraph checks amendments                    # every registered act
    legalgraph checks amendments EU DE              # a jurisdiction group
    legalgraph checks amendments EU-2016-679 DE-UWG # single acts
"""

from legalgraph.amendments.compare import compare, run
from legalgraph.amendments.graph import graph_checks
from legalgraph.amendments.model import GraphCheck, LiveAmendment, Result
from legalgraph.amendments.registry import checker_kinds, exempt_acts, fetch_live, live_checks, registry

__all__ = [
    "GraphCheck",
    "LiveAmendment",
    "Result",
    "checker_kinds",
    "compare",
    "exempt_acts",
    "fetch_live",
    "graph_checks",
    "live_checks",
    "registry",
    "run",
]
