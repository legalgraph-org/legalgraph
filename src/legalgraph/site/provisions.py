"""The site's provisions collection: each provision with its quotes and its links to others."""

from typing import Any

from rdflib import RDF, RDFS, Graph, Literal
from rdflib.term import Node

from legalgraph import ELI, LGO
from legalgraph.site.values import (
    act_jurisdiction,
    english_texts,
    inverse,
    language_versions,
    name,
    names,
    one,
    translation_of,
)


def quote_entry(graph: Graph, quote: Node) -> dict[str, Any]:
    text = graph.value(quote, LGO.text)
    return {
        "id": name(quote),
        "lang": text.language if isinstance(text, Literal) else "",
        "text": str(text),
        "sourceUrl": one(graph, quote, LGO.sourceUrl),
        "retrievedOn": one(graph, quote, LGO.retrievedOn),
        "official": one(graph, quote, LGO.officialLanguageVersion) != "false",
        "translation": translation_of(graph, quote),
        "versions": language_versions(graph, quote),
    }


def quotes(graph: Graph, provision: Node) -> list[dict[str, Any]]:
    """The provision's quotes; a language version is shown with the quote it is a version of."""
    return [
        quote_entry(graph, quote)
        for quote in sorted(graph.subjects(LGO.quoteOf, provision), key=str)
        if graph.value(quote, LGO.languageVersionOf) is None
    ]


def provision_entry(graph: Graph, provision: Node) -> dict[str, Any]:
    act = graph.value(provision, ELI.is_part_of)
    document = graph.value(provision, LGO.sourceDocument)
    return {
        "id": name(provision),
        "citation": one(graph, provision, LGO.citation),
        "act": name(act),
        "jurisdiction": act_jurisdiction(graph, act),
        "sourceUrl": one(graph, provision, LGO.sourceUrl),
        "reviewStatus": name(graph.value(provision, LGO.reviewStatus)),
        "regulates": names(graph, provision, LGO.regulates),
        "enforces": names(graph, provision, LGO.enforces),
        "defines": names(graph, provision, LGO.defines),
        "authorises": names(graph, provision, LGO.authorises),
        "requires": names(graph, provision, LGO.requiresDisclosureOf),
        "implements": names(graph, provision, LGO.implements),
        "implementedBy": inverse(graph, provision, LGO.implements),
        "explains": names(graph, provision, LGO.explains),
        "interprets": names(graph, provision, LGO.interprets),
        "interpretedBy": inverse(graph, provision, LGO.interprets),
        "specifies": names(graph, provision, LGO.specifies),
        "specifiedBy": inverse(graph, provision, LGO.specifies),
        "takesPrecedenceOver": names(graph, provision, LGO.takesPrecedenceOver),
        "givesWayTo": inverse(graph, provision, LGO.takesPrecedenceOver),
        "refersTo": names(graph, provision, LGO.refersTo),
        "referredToBy": inverse(graph, provision, LGO.refersTo),
        "proposesToAmend": names(graph, provision, LGO.proposesToAmend),
        "proposedAmendments": inverse(graph, provision, LGO.proposesToAmend),
        "applies": names(graph, provision, LGO.applies),
        "appliedBy": inverse(graph, provision, LGO.applies),
        "penalises": names(graph, provision, LGO.penalises),
        "penalisedBy": inverse(graph, provision, LGO.penalises),
        "continues": names(graph, provision, LGO.continues),
        "continuedBy": inverse(graph, provision, LGO.continues),
        "readUnder": names(graph, provision, LGO.readUnder),
        "readUnderBy": inverse(graph, provision, LGO.readUnder),
        "comments": english_texts(graph, provision, RDFS.comment),
        "document": name(document) if document else None,
        "sourceElement": one(graph, provision, LGO.sourceElement),
        "quotes": quotes(graph, provision),
    }


def provisions(graph: Graph) -> list[dict[str, Any]]:
    return sorted(
        (provision_entry(graph, provision) for provision in graph.subjects(RDF.type, LGO.Provision)),
        key=lambda p: p["id"],
    )
