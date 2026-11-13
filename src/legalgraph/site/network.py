"""Nodes and edges for the site's interactive view of the graph."""

from typing import Any

from rdflib import RDF, SKOS, Graph
from rdflib.term import Node

from legalgraph import ELI, LGO
from legalgraph.site.values import label, name, one

EDGES = [
    (LGO.jurisdiction, "enacted in"),
    (LGO.memberOf, "member of"),
    (LGO.subdivisionOf, "subdivision of"),
    (ELI.is_part_of, "part of"),
    (ELI.transposes, "transposes"),
    (ELI.repeals, "repeals"),
    (LGO.implements, "implements"),
    (LGO.regulates, "regulates"),
    (LGO.enforces, "enforces"),
    (LGO.defines, "defines"),
    (LGO.authorises, "authorises"),
    (LGO.requiresDisclosureOf, "requires"),
    (LGO.explains, "explains"),
    (LGO.interprets, "interprets"),
    (LGO.specifies, "specifies"),
    (LGO.takesPrecedenceOver, "takes precedence over"),
    (LGO.refersTo, "refers to"),
    (LGO.proposesToAmend, "proposes to amend"),
    (LGO.applies, "applies"),
    (LGO.penalises, "penalises"),
    (LGO.continues, "continues"),
    (LGO.readUnder, "read under"),
    (LGO.illustrates, "illustrates"),
    (LGO.follows, "follows"),
    (LGO.establishedBy, "established by"),
    (SKOS.broader, "broader"),
]
NODE_TYPES = [
    (LGO.SupranationalOrganisation, "organisation"),
    (LGO.Country, "country"),
    (LGO.Subdivision, "country"),  # California, Ontario: drawn as countries, tied to theirs by "subdivision of"
    (LGO.LegalAct, "act"),
    (LGO.CourtDecision, "decision"),
    (LGO.AuthorityDecision, "decision"),
    (LGO.Guidance, "guidance"),
    (LGO.Provision, "provision"),
    (LGO.DisclosureType, "disclosure"),
    (LGO.InformationItem, "item"),
    (LGO.LegalConcept, "concept"),
    (LGO.Obligation, "rule"),
]


def network(graph: Graph) -> dict[str, Any]:
    """Nodes and edges for the interactive view (text-only resources such as quotes are left out)."""
    types: dict[Node, str] = {}
    for cls, kind in NODE_TYPES:
        for node in graph.subjects(RDF.type, cls):
            types.setdefault(node, kind)
    nodes = []
    for node, kind in types.items():
        text = label(graph, node)
        if kind in ("act", "decision", "guidance"):
            text = one(graph, node, LGO.shortName) or text
        elif kind in ("country", "organisation"):
            text = one(graph, node, LGO.isoCode) or text
        nodes.append({"id": name(node), "label": text, "title": label(graph, node), "type": kind})
    edges = []
    for predicate, text in EDGES:
        for s, o in graph.subject_objects(predicate):
            if s in types and o in types:
                edges.append({"source": name(s), "target": name(o), "label": text})
    return {
        "nodes": sorted(nodes, key=lambda n: n["id"]),
        "edges": sorted(edges, key=lambda e: (e["source"], e["label"], e["target"])),
    }
