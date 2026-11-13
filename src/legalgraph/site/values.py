"""Reading values out of the graph as the site's JSON wants them."""

from typing import Any

from rdflib import RDFS, SKOS, Graph, Literal, URIRef
from rdflib.term import Node

from legalgraph import LG, LGO, LGV
from legalgraph.localisation import sha256


def name(node: Node) -> str:
    text = str(node)
    for namespace in (LG, LGV):
        if text.startswith(str(namespace)):
            return text.removeprefix(str(namespace))
    return text


def texts(graph: Graph, subject: Node, predicate: URIRef) -> list[dict[str, str]]:
    values = [o for o in graph.objects(subject, predicate) if isinstance(o, Literal)]
    return sorted(({"text": str(v), "lang": v.language or ""} for v in values), key=lambda t: (t["lang"], t["text"]))


def one(graph: Graph, subject: Node, predicate: URIRef) -> str | None:
    value = graph.value(subject, predicate)
    return None if value is None else str(value)


def names(graph: Graph, subject: Node, predicate: URIRef) -> list[str]:
    return sorted(name(o) for o in graph.objects(subject, predicate))


def inverse(graph: Graph, obj: Node, predicate: URIRef) -> list[str]:
    return sorted(name(s) for s in graph.subjects(predicate, obj))


def english(graph: Graph, subject: Node, predicate: URIRef, value: Literal) -> str | None:
    """English for a literal: the value itself, an @en sibling, or its lgo:Translation."""
    if value.language in (None, "en"):
        return str(value)
    for other in graph.objects(subject, predicate):
        if isinstance(other, Literal) and other.language == "en":
            return str(other)
    digest = sha256(str(value))
    for node in graph.subjects(LGO.translationOf, subject):
        if (
            graph.value(node, LGO.translatedProperty) == predicate
            and str(graph.value(node, LGO.sourceTextSha256)) == digest
        ):
            return one(graph, node, LGO.text)
    return None


def label(graph: Graph, node: Node) -> str:
    for predicate in (SKOS.prefLabel, RDFS.label, LGO.citation, LGO.shortName):
        values = [o for o in graph.objects(node, predicate) if isinstance(o, Literal)]
        english_values = [v for v in values if v.language in (None, "en")]
        if english_values or values:
            return str(sorted(english_values or values, key=str)[0])
    return name(node)


def translation_of(graph: Graph, quote: Node) -> dict[str, Any] | None:
    node = graph.value(None, LGO.translationOf, quote)
    if node is None or graph.value(node, LGO.translatedProperty) is not None:
        return None
    return {
        "text": one(graph, node, LGO.text),
        "method": name(graph.value(node, LGO.translationMethod)),
        "by": sorted(map(str, graph.objects(node, LGO.translatedBy))),
        "on": one(graph, node, LGO.translatedOn),
        "status": name(graph.value(node, LGO.reviewStatus)),
        "reviewedBy": sorted(map(str, graph.objects(node, LGO.reviewedBy))),
    }


def language_versions(graph: Graph, quote: Node) -> list[dict[str, Any]]:
    """The quote's text in the other official languages (lgo:languageVersionOf)."""
    versions = []
    for version in sorted(graph.subjects(LGO.languageVersionOf, quote), key=str):
        text = graph.value(version, LGO.text)
        versions.append(
            {
                "id": name(version),
                "lang": text.language if isinstance(text, Literal) else "",
                "text": str(text),
                "sourceUrl": one(graph, version, LGO.sourceUrl),
                "official": one(graph, version, LGO.officialLanguageVersion) != "false",
            }
        )
    return versions


def act_jurisdiction(graph: Graph, act: Node) -> str:
    return name(graph.value(act, LGO.jurisdiction))


def english_text(graph: Graph, subject: Node, predicate: URIRef) -> str | None:
    """The @en value of a property, if it has one."""
    return next((t["text"] for t in texts(graph, subject, predicate) if t["lang"] == "en"), None)


def english_texts(graph: Graph, subject: Node, predicate: URIRef) -> list[dict[str, str]]:
    return [t for t in texts(graph, subject, predicate) if t["lang"] == "en"]
