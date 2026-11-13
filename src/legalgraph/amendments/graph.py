"""The lgo:AmendmentCheck data the graph holds for each act."""

from collections.abc import Callable
from typing import Any

from rdflib import Graph
from rdflib.term import Node

from legalgraph import LG, LGO
from legalgraph.amendments.model import GraphCheck, parse_date

SUFFIX = "-amendment-check"

# lgo: property -> (GraphCheck field, how to read the value)
FIELDS: dict[str, tuple[str, Callable[[Node], Any]]] = {
    "checkedOn": ("checked_on", lambda o: parse_date(str(o))),
    "sourceUrl": ("source_url", str),
    "lastKnownAmendment": ("citation", str),
    "lastKnownAmendmentDate": ("amendment_date", lambda o: parse_date(str(o))),
    "lastKnownAmendmentInForce": ("in_force", lambda o: parse_date(str(o))),
    "sourceIsCurrent": ("current", lambda o: str(o).lower() in ("true", "1")),
}


def graph_check(graph: Graph, subject: Node) -> GraphCheck:
    check = GraphCheck()
    for predicate, value in graph.predicate_objects(subject):
        local = str(predicate).removeprefix(str(LGO))
        if local in FIELDS:
            field, read = FIELDS[local]
            setattr(check, field, read(value))
        elif str(predicate).endswith("comment"):
            check.comment = str(value)
    return check


def graph_checks(graph: Graph) -> dict[str, GraphCheck]:
    """All lgo:AmendmentCheck data in the graph, keyed by act id."""
    return {
        str(subject).removeprefix(str(LG)).removesuffix(SUFFIX): graph_check(graph, subject)
        for subject in set(graph.subjects())
        if str(subject).startswith(str(LG)) and str(subject).endswith(SUFFIX)
    }
