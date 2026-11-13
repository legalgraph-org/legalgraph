"""Reasoning: the SHACL rules of ontology/rules/reasoning/ add the triples that follow from the graph.

Validation runs on the inferred graph, so shapes can rely on derived properties such as lgo:within
instead of walking lgo:memberOf and lgo:subdivisionOf themselves. Properties marked lgo:inferred are
produced only here: the data must not state them.
"""

from pyshacl import shacl_rules
from rdflib import Graph, Literal, URIRef

from legalgraph import LGO
from legalgraph.load import Sources, parse_files


def load_rules(sources: Sources) -> Graph:
    """The reasoning rules. Syntax errors surface in validation, which parses the same files."""
    rules, _ = parse_files(sources.reasoning_files)
    return rules


def infer(graph: Graph, rules: Graph) -> Graph:
    """A copy of the graph with everything the rules infer, applied until nothing new follows."""
    inferred = Graph()
    inferred += graph
    if len(rules):
        shacl_rules(inferred, shacl_graph=rules, inplace=True, iterate_rules=True)
    return inferred


def inferred_properties(ontology: Graph) -> set[URIRef]:
    return {p for p in ontology.subjects(LGO.inferred, Literal(True)) if isinstance(p, URIRef)}


def stated_inferences(data: Graph, ontology: Graph) -> list[str]:
    """Data that states a property only the reasoning rules may produce."""
    problems = set()
    for prop in inferred_properties(ontology):
        for subject in data.subjects(prop, None):
            problems.add(f"{data.qname(subject)} states {data.qname(prop)}, which only the reasoning rules infer")
    return sorted(problems)
