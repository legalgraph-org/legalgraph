"""Hygiene of the ontology's files: the folder layout, one class per file named after it, properties
next to their class, and one shape or rule per file named after it. The file list then reads as the
ontology's table of contents."""

from pathlib import Path

from rdflib import OWL, RDF, RDFS, BNode, Graph, URIRef
from rdflib.namespace import SH

from legalgraph import LGO
from legalgraph.hygiene.model import Finding, Rule, line_of

LGS = "https://legalgraph.org/shapes#"
LAYOUT = {
    "ontology.ttl": "the ontology's header (owl:Ontology)",
    "README.md": None,
    "LICENSE": None,
    "classes": "one file per class, with the properties whose domain it is",
    "properties": "one file per property without a single class as its domain",
    "vocab": "SKOS vocabularies: the terms the data uses",
    "annotations": "annotations on terms, such as which properties need English",
    "rules": "rules/reasoning (SHACL rules that infer) and rules/validation (SHACL shapes)",
}
RULE_FOLDERS = {"reasoning", "validation"}
PROPERTY_TYPES = (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)


def turtle(path: Path) -> Graph:
    return Graph().parse(path, format="turtle")


def local(node: URIRef) -> str:
    return str(node).removeprefix(str(LGO)).removeprefix(LGS)


def own_terms(graph: Graph, types: tuple[URIRef, ...]) -> list[URIRef]:
    return sorted(
        {s for t in types for s in graph.subjects(RDF.type, t) if isinstance(s, URIRef) and str(s).startswith(LGO)}
    )


def home(graph: Graph, prop: URIRef) -> str:
    """Where a property belongs: its domain class's file, or a file of its own."""
    domains = list(graph.objects(prop, RDFS.domain))
    if len(domains) == 1 and not isinstance(domains[0], BNode) and str(domains[0]).startswith(LGO):
        return f"classes/{local(domains[0])}.ttl"
    return f"properties/{local(prop)}.ttl"


def layout(root: Path) -> list[Finding]:
    folder = root / "ontology"
    findings = [
        Finding(path, 1, "ONT001", f"not part of the ontology layout ({', '.join(LAYOUT)})")
        for path in sorted(folder.iterdir())
        if path.name not in LAYOUT
    ]
    rules = folder / "rules"
    if rules.is_dir():
        findings += [
            Finding(path, 1, "ONT001", "rules/ holds reasoning/ and validation/ only")
            for path in sorted(rules.iterdir())
            if path.name not in RULE_FOLDERS
        ]
    for sub in ("classes", "properties", "vocab", "annotations", "rules/reasoning", "rules/validation"):
        if (folder / sub).is_dir():
            findings += [
                Finding(path, 1, "ONT001", f"{sub}/ holds Turtle files only, no folders or other files")
                for path in sorted((folder / sub).iterdir())
                if path.is_dir() or path.suffix != ".ttl"
            ]
    return findings


def ontology_files(root: Path) -> list[Path]:
    rules = root / "ontology" / "rules"
    return sorted(path for path in (root / "ontology").rglob("*.ttl") if not path.is_relative_to(rules))


def class_files(root: Path) -> list[Finding]:
    findings = []
    for path in ontology_files(root):
        relative = path.relative_to(root / "ontology").as_posix()
        classes = own_terms(turtle(path), (OWL.Class,))
        if relative.startswith("classes/"):
            if [local(c) for c in classes] != [path.stem]:
                found = ", ".join(local(c) for c in classes) or "none"
                findings.append(
                    Finding(path, 1, "ONT002", f"defines {found}; a class file defines lgo:{path.stem} only")
                )
            continue
        findings += [
            Finding(
                path, line_of(path, f"lgo:{local(c)} "), "ONT002", f"lgo:{local(c)} belongs in classes/{local(c)}.ttl"
            )
            for c in classes
        ]
    return findings


def property_files(root: Path) -> list[Finding]:
    findings = []
    for path in ontology_files(root):
        graph = turtle(path)
        relative = path.relative_to(root / "ontology").as_posix()
        properties = own_terms(graph, PROPERTY_TYPES)
        for prop in properties:
            if home(graph, prop) != relative:
                where = line_of(path, f"lgo:{local(prop)} ")
                findings.append(Finding(path, where, "ONT003", f"lgo:{local(prop)} belongs in {home(graph, prop)}"))
        if relative.startswith("properties/") and len(properties) != 1:
            findings.append(Finding(path, 1, "ONT003", "a property file defines exactly one property"))
    return findings


def rule_files(root: Path) -> list[Finding]:
    findings = []
    for kind in RULE_FOLDERS:
        for path in sorted((root / "ontology" / "rules" / kind).glob("*.ttl")):
            graph = turtle(path)
            shapes = sorted(local(s) for s in graph.subjects(RDF.type, SH.NodeShape) if isinstance(s, URIRef))
            if shapes != [path.stem]:
                message = f"defines {', '.join(shapes) or 'no shape'}; the file defines lgs:{path.stem} only"
                findings.append(Finding(path, 1, "ONT004", message))
            inferring = any(graph.subjects(SH.rule, None))
            if inferring != (kind == "reasoning"):
                message = "reasoning/ holds sh:rule shapes, validation/ shapes without sh:rule"
                findings.append(Finding(path, 1, "ONT004", message))
    return findings


RULES = [
    Rule("ONT001", "The ontology folder holds only the agreed layout.", layout),
    Rule("ONT002", "Each class is defined in classes/<ClassName>.ttl, alone.", class_files),
    Rule("ONT003", "A property sits in its domain class's file, else in properties/<name>.ttl.", property_files),
    Rule("ONT004", "Each file in rules/ defines one shape named after it; only reasoning/ infers.", rule_files),
]
