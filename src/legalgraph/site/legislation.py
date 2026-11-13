"""The site's collections of jurisdictions, legal documents and their source documents."""

import re
from datetime import datetime
from typing import Any

from rdflib import DCTERMS, RDF, RDFS, Graph, Literal
from rdflib.term import Node

from legalgraph import ELI, LGO
from legalgraph.site.values import (
    act_jurisdiction,
    english,
    english_text,
    english_texts,
    inverse,
    label,
    name,
    names,
    one,
    texts,
)

DOCUMENT_KINDS = {
    LGO.LegalAct: "act",
    LGO.CourtDecision: "decision",
    LGO.AuthorityDecision: "enforcement",
    LGO.Guidance: "guidance",
}

# When the text was last changed, as the notes on its source documents state it (lgo:legalStatus):
# gesetze-im-internet.de's "Zuletzt geändert durch … v. 20.7.2026" and "Änderung durch … v. … textlich
# nachgewiesen" (an amendment already worked into the text), and the date of an EU consolidated text.
AMENDED_DE = re.compile(r"(?:zuletzt geändert|Änderung) durch .*? v\. (\d{1,2})\.(\d{1,2})\.(\d{4})", re.IGNORECASE)
CONSOLIDATED_EU = re.compile(r"^Consolidated text (?:applying from|as of) (\d{1,2} [A-Z][a-z]+ \d{4})")


def jurisdictions(graph: Graph) -> list[dict[str, Any]]:
    result = []
    for kind, cls in (
        ("organisation", LGO.SupranationalOrganisation),
        ("country", LGO.Country),
        ("subdivision", LGO.Subdivision),
    ):
        for node in graph.subjects(RDF.type, cls):
            acts = inverse(graph, node, LGO.jurisdiction)
            result.append(
                {
                    "id": name(node),
                    "code": one(graph, node, LGO.isoCode),
                    "kind": kind,
                    "label": label(graph, node),
                    "memberOf": names(graph, node, LGO.memberOf) + names(graph, node, LGO.subdivisionOf),
                    "members": inverse(graph, node, LGO.memberOf) + inverse(graph, node, LGO.subdivisionOf),
                    "languages": sorted(map(str, graph.objects(node, LGO.officialLanguage))),
                    "noticeNames": texts(graph, node, LGO.customaryNoticeName),
                    "comment": english_text(graph, node, RDFS.comment),
                    "acts": acts,
                }
            )
    return sorted(result, key=lambda j: (j["kind"] != "organisation", j["label"]))


def outcome(graph: Graph, node: Node) -> dict[str, Any]:
    """What a decision ordered for one party, with the point of the decision that states it."""
    amount = graph.value(node, LGO.amount)
    return {
        "id": name(node),
        "type": label(graph, graph.value(node, LGO.outcomeType)),
        "against": sorted(map(str, graph.objects(node, LGO.against))),
        "amount": None if amount is None else float(amount),
        "currency": one(graph, node, LGO.currency),
        "statedIn": names(graph, node, LGO.statedIn),
        "forBreachOf": names(graph, node, LGO.forBreachOf),
        "sanctionedUnder": names(graph, node, LGO.sanctionedUnder),
        "comment": english_text(graph, node, RDFS.comment),
        "reviewStatus": name(graph.value(node, LGO.reviewStatus)),
    }


def references(graph: Graph, targets: list[Node]) -> list[dict[str, Any]]:
    """Link-only pages (someone else's work) that back up any of the targets."""
    found = sorted({ref for target in targets for ref in graph.subjects(LGO.supports, target)}, key=str)
    result = []
    for ref in found:
        excerpt = graph.value(ref, LGO.excerpt)
        result.append(
            {
                "id": name(ref),
                "title": one(graph, ref, DCTERMS.title),
                "publisher": one(graph, ref, DCTERMS.publisher),
                "url": one(graph, ref, LGO.sourceUrl),
                "date": one(graph, ref, DCTERMS.date),
                "excerpt": None if excerpt is None else str(excerpt),
                "excerptLang": excerpt.language if isinstance(excerpt, Literal) else None,
                "locator": one(graph, ref, LGO.excerptLocator),
                "claim": english_text(graph, ref, RDFS.comment),
            }
        )
    return result


def last_amended(graph: Graph, act: Node) -> str | None:
    dates = []
    for document in graph.objects(act, LGO.sourceDocument):
        for note in graph.objects(document, LGO.legalStatus):
            if match := AMENDED_DE.search(str(note)):
                day, month, year = match.groups()
                dates.append(f"{year}-{int(month):02d}-{int(day):02d}")
            elif match := CONSOLIDATED_EU.search(str(note)):
                dates.append(datetime.strptime(match.group(1), "%d %B %Y").date().isoformat())
    return max(dates, default=None)


def english_title(graph: Graph, act: Node, titles: list[dict[str, str]]) -> str | None:
    title = next((t["text"] for t in titles if t["lang"] == "en"), None)
    if title is not None:
        return title
    original = next((v for v in graph.objects(act, ELI.title) if isinstance(v, Literal)), None)
    return english(graph, act, ELI.title, original) if original is not None else None


def act_entry(graph: Graph, act: Node, kind: str) -> dict[str, Any]:
    titles = texts(graph, act, ELI.title)
    return {
        "id": name(act),
        "kind": kind,
        "ecli": one(graph, act, LGO.ecli),
        "titles": titles,
        "titleEn": english_title(graph, act, titles),
        "shortName": one(graph, act, LGO.shortName),
        "actType": label(graph, graph.value(act, LGO.actType)),
        "jurisdiction": act_jurisdiction(graph, act),
        "sourceUrl": one(graph, act, LGO.sourceUrl),
        "localId": one(graph, act, ELI.id_local),
        "dateDocument": one(graph, act, ELI.date_document),
        "lastAmended": last_amended(graph, act),
        "firstInForce": one(graph, act, ELI.first_date_entry_in_force),
        "noLongerInForce": one(graph, act, ELI.date_no_longer_in_force),
        "transposes": names(graph, act, ELI.transposes),
        "transposedBy": inverse(graph, act, ELI.transposes),
        "repeals": names(graph, act, ELI.repeals),
        "repealedBy": sorted(set(names(graph, act, ELI.repealed_by) + inverse(graph, act, ELI.repeals))),
        "authorisedBy": inverse(graph, act, LGO.authorises),
        "reviewStatus": name(graph.value(act, LGO.reviewStatus)),
        "comments": english_texts(graph, act, RDFS.comment),
        "documents": names(graph, act, LGO.sourceDocument),
        "provisions": sorted(inverse(graph, act, ELI.is_part_of)),
        "caseNumber": one(graph, act, LGO.caseNumber),
        "creator": one(graph, act, DCTERMS.creator),
        "outcomes": [outcome(graph, o) for o in sorted(graph.objects(act, LGO.hasOutcome), key=str)],
        "illustrates": names(graph, act, LGO.illustrates),
        "follows": names(graph, act, LGO.follows),
        "followedBy": inverse(graph, act, LGO.follows),
        "references": references(graph, [act, *graph.objects(act, LGO.hasOutcome)]),
    }


def acts(graph: Graph) -> list[dict[str, Any]]:
    """Legal acts, court decisions and guidance: the documents provisions are part of."""
    found = ((act, kind) for cls, kind in DOCUMENT_KINDS.items() for act in graph.subjects(RDF.type, cls))
    return sorted((act_entry(graph, act, kind) for act, kind in found), key=lambda a: a["id"])


def legal_status(graph: Graph, document: Node) -> list[dict[str, Any]]:
    notes = [
        {"text": str(value), "lang": value.language or "", "english": english(graph, document, LGO.legalStatus, value)}
        for value in graph.objects(document, LGO.legalStatus)
        if isinstance(value, Literal)
    ]
    return sorted(notes, key=lambda n: n["text"])


def document_entry(graph: Graph, document: Node) -> dict[str, Any]:
    version_of = graph.value(document, LGO.languageVersionOf)
    licence = graph.value(document, LGO.licence)
    return {
        "id": name(document),
        "act": next(
            name(s)
            for s in sorted(graph.subjects(LGO.sourceDocument, document), key=str)
            if any((s, RDF.type, cls) in graph for cls in DOCUMENT_KINDS)
        ),
        "path": one(graph, document, LGO.repositoryPath),
        "annotatedFile": one(graph, document, LGO.annotatedFile),
        "sha256": one(graph, document, LGO.sha256),
        "sourceUrl": one(graph, document, LGO.sourceUrl),
        "retrievedOn": one(graph, document, LGO.retrievedOn),
        "mediaType": one(graph, document, LGO.mediaType),
        "portalBuildDate": one(graph, document, LGO.portalBuildDate),
        "language": one(graph, document, DCTERMS.language),
        "versionOf": name(version_of) if version_of else None,
        "versions": inverse(graph, document, LGO.languageVersionOf),
        "legalStatus": legal_status(graph, document),
        "licence": label(graph, licence) if licence else None,
        "licenceBasis": one(graph, document, LGO.licenceBasis),
    }


def documents(graph: Graph) -> list[dict[str, Any]]:
    return sorted(
        (document_entry(graph, document) for document in graph.subjects(RDF.type, LGO.SourceDocument)),
        key=lambda d: d["id"],
    )
