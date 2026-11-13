"""Validation: Turtle syntax, SHACL shapes, references to undefined terms, and missing English translations."""

from dataclasses import dataclass, field

from pyshacl import validate as shacl_validate
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import SH
from rdflib.term import Node

from legalgraph import LG, LGO, LGV
from legalgraph.load import Sources, load_all
from legalgraph.localisation import describe, line_mismatches, orphans, pending
from legalgraph.reasoning import infer, load_rules, stated_inferences


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    triples: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def qname(graph: Graph, node: Node) -> str:
    return graph.qname(node) if isinstance(node, URIRef) else str(node)


def undefined_terms(data: Graph, ontology: Graph) -> list[str]:
    """lgo:/lgv: terms the ontology does not define, and lg: resources referenced but never typed."""
    defined = set(ontology.subjects())
    typed = set(data.subjects(RDF.type))
    problems: set[str] = set()
    for subject, predicate, obj in data:
        if isinstance(predicate, URIRef) and predicate.startswith(LGO) and predicate not in defined:
            problems.add(f"Undefined property {qname(data, predicate)} (used on {qname(data, subject)})")
        if not isinstance(obj, URIRef):
            continue
        if obj.startswith(LGO) and obj not in defined:
            problems.add(f"Undefined class {qname(data, obj)} (used on {qname(data, subject)})")
        if obj.startswith(LGV) and obj not in defined:
            problems.add(f"Undefined vocabulary term {qname(data, obj)} (used on {qname(data, subject)})")
        if obj.startswith(LG) and obj not in typed:
            problems.add(f"{qname(data, subject)} refers to {qname(data, obj)}, which no data file defines")
    return sorted(problems)


def shacl_results(data: Graph, ontology: Graph, shapes: Graph, rules: Graph) -> tuple[list[str], list[str]]:
    """Violations and warnings of the shapes, on the data with the ontology and everything the rules infer."""
    # The ontology is merged into the data graph here rather than passed as ont_graph: pyshacl's own
    # mixing left vocabulary types invisible to some sh:class and SPARQL constraints (pyshacl 0.40).
    merged = Graph()
    merged += data
    merged += ontology
    conforms, results, _ = shacl_validate(infer(merged, rules), shacl_graph=shapes, inference="rdfs")
    if conforms:
        return [], []
    found: dict[Node, set[str]] = {SH.Violation: set(), SH.Warning: set()}
    for result in results.subjects(RDF.type, SH.ValidationResult):
        severity = results.value(result, SH.resultSeverity)
        found.setdefault(severity, set()).add(result_message(data, results, result))
    return sorted(found[SH.Violation]), sorted(found[SH.Warning])


def result_message(data: Graph, results: Graph, result: Node) -> str:
    focus = results.value(result, SH.focusNode)
    path = results.value(result, SH.resultPath)
    value = results.value(result, SH.value)
    message = results.value(result, SH.resultMessage)
    where = qname(data, focus) if focus is not None else "?"
    if isinstance(path, URIRef):
        where += f" {qname(data, path)}"
    if isinstance(value, URIRef):
        where += f" ({qname(data, value)})"
    text = str(message) if isinstance(message, Literal) else "violates a shape"
    return f"{where}: {text}"


def shacl_violations(data: Graph, ontology: Graph, shapes: Graph, rules: Graph) -> list[str]:
    return shacl_results(data, ontology, shapes, rules)[0]


def validate(sources: Sources) -> Report:
    data, ontology, shapes, parse_errors = load_all(sources)
    report = Report(triples=len(data))
    report.errors += [f"{error.path}: {error.message}" for error in parse_errors]
    if parse_errors:
        return report
    report.errors += undefined_terms(data, ontology)
    report.errors += stated_inferences(data, ontology)
    violations, warnings = shacl_results(data, ontology, shapes, load_rules(sources))
    report.errors += violations
    report.warnings += warnings
    report.errors += [describe(item, data) for item in pending(data, ontology)]
    report.errors += orphans(data)
    report.errors += line_mismatches(data)
    return report
