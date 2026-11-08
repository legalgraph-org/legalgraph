"""A small deterministic Turtle writer for generated files: same graph, same bytes, readable diffs.

rdflib's own serializer does not promise a stable order across versions, which would make
`legalgraph sources extract --check` flaky. Here subjects are sorted by IRI, rdf:type comes first, then
predicates and objects in sorted order, and multi-line text is written as a triple-quoted literal.
"""

import re

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDFS, SKOS, XSD
from rdflib.term import Node

from legalgraph import ELI, LG, LGO, LGV

NAMESPACES = {
    "lgo": LGO,
    "lgv": LGV,
    "lg": LG,
    "eli": ELI,
    "dcterms": DCTERMS,
    "rdfs": RDFS,
    "skos": SKOS,
    "xsd": XSD,
}
LOCAL_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")


def term(node: Node) -> str:
    if isinstance(node, URIRef):
        if node == RDF.type:
            return "a"
        for prefix, namespace in NAMESPACES.items():
            local = node.removeprefix(str(namespace))
            if local != node and LOCAL_NAME.match(local):
                return f"{prefix}:{local}"
        return f"<{node}>"
    if isinstance(node, Literal):
        return literal(node)
    raise ValueError(f"Cannot write {node!r}")


def literal(value: Literal) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    quoted = f'"""{text}"""' if "\n" in text else f'"{text}"'
    if value.language:
        return f"{quoted}@{value.language}"
    if value.datatype in (None, XSD.string):
        return quoted
    if value.datatype == XSD.boolean:
        return str(value).lower()
    return f"{quoted}^^{term(value.datatype)}"


def serialize(graph: Graph, comment: str) -> str:
    lines = [f"# {line}".rstrip() for line in comment.strip().splitlines()]
    lines.append("")
    lines += [f"@prefix {prefix}: <{namespace}> ." for prefix, namespace in sorted(NAMESPACES.items())]
    for subject in sorted(set(graph.subjects()), key=str):
        predicates = sorted(set(graph.predicates(subject)), key=lambda p: (p != RDF.type, term(p)))
        statements = []
        for predicate in predicates:
            objects = sorted(term(obj) for obj in graph.objects(subject, predicate))
            statements.append(f"    {term(predicate)} {' , '.join(objects)}")
        lines.append("")
        lines.append(f"{term(subject)}\n" + " ;\n".join(statements) + " .")
    return "\n".join(lines) + "\n"
