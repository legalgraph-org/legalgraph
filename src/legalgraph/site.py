"""Data for the browsable site in site/ (Astro).

Python owns the meaning, Astro the presentation. This module reads the graph and writes:

- site/src/data/*.json: one JSON file per collection (jurisdictions, acts, provisions, concepts,
  documents) plus the graph for the interactive view and summary numbers. Astro loads them as
  content collections and validates them with Zod schemas (site/src/content.config.ts).
- site/public/id/<name>.ttl, site/public/vocab/<name>.ttl: the triples about each resource, so
  every identifier can also be served as Turtle (see site/worker/ for content negotiation).
- site/public/downloads/: the whole graph as Turtle, N-Triples and JSON-LD, and the ontology.
- site/public/sources/: the law texts and their indexes, so a reader can check them in the browser.

Output is deterministic: the same graph gives the same files.
"""

import importlib.metadata
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from rdflib import DCTERMS, OWL, RDF, RDFS, SKOS, Graph, Literal, URIRef
from rdflib.term import Node

from legalgraph import ELI, LG, LGO, LGV, rules
from legalgraph.load import REPO_ROOT, Sources, load_all, new_graph
from legalgraph.localisation import sha256
from legalgraph.sources import load_sources, reading_view, repo_path
from legalgraph.turtle import serialize

SITE_DIR = REPO_ROOT / "site"
DATA_DIR = SITE_DIR / "src" / "data"
PUBLIC_DIR = SITE_DIR / "public"
GENERATED_PUBLIC = ("id", "vocab", "downloads", "sources")
ONTOLOGY_IRI = "https://legalgraph.org/ontology"


class SiteError(Exception):
    pass


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


# --- Collections ---------------------------------------------------------------


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
                    "comment": next((t["text"] for t in texts(graph, node, RDFS.comment) if t["lang"] == "en"), None),
                    "acts": acts,
                }
            )
    return sorted(result, key=lambda j: (j["kind"] != "organisation", j["label"]))


DOCUMENT_KINDS = {
    LGO.LegalAct: "act",
    LGO.CourtDecision: "decision",
    LGO.AuthorityDecision: "enforcement",
    LGO.Guidance: "guidance",
}


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
        "comment": next((t["text"] for t in texts(graph, node, RDFS.comment) if t["lang"] == "en"), None),
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
                "claim": next((t["text"] for t in texts(graph, ref, RDFS.comment) if t["lang"] == "en"), None),
            }
        )
    return result


# When the text was last changed, as the notes on its source documents state it (lgo:legalStatus):
# gesetze-im-internet.de's "Zuletzt geändert durch … v. 20.7.2026" and "Änderung durch … v. … textlich
# nachgewiesen" (an amendment already worked into the text), and the date of an EU consolidated text.
AMENDED_DE = re.compile(r"(?:zuletzt geändert|Änderung) durch .*? v\. (\d{1,2})\.(\d{1,2})\.(\d{4})", re.IGNORECASE)
CONSOLIDATED_EU = re.compile(r"^Consolidated text (?:applying from|as of) (\d{1,2} [A-Z][a-z]+ \d{4})")


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


def acts(graph: Graph) -> list[dict[str, Any]]:
    """Legal acts, court decisions and guidance: the documents provisions are part of."""
    result = []
    for act, kind in ((a, k) for cls, k in DOCUMENT_KINDS.items() for a in graph.subjects(RDF.type, cls)):
        titles = texts(graph, act, ELI.title)
        title_en = next((t["text"] for t in titles if t["lang"] == "en"), None)
        if title_en is None:
            original = next((v for v in graph.objects(act, ELI.title) if isinstance(v, Literal)), None)
            title_en = english(graph, act, ELI.title, original) if original is not None else None
        result.append(
            {
                "id": name(act),
                "kind": kind,
                "ecli": one(graph, act, LGO.ecli),
                "titles": titles,
                "titleEn": title_en,
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
                "comments": [t for t in texts(graph, act, RDFS.comment) if t["lang"] == "en"],
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
        )
    return sorted(result, key=lambda a: a["id"])


def provisions(graph: Graph) -> list[dict[str, Any]]:
    result = []
    for provision in graph.subjects(RDF.type, LGO.Provision):
        act = graph.value(provision, ELI.is_part_of)
        quotes = []
        for quote in sorted(graph.subjects(LGO.quoteOf, provision), key=str):
            if graph.value(quote, LGO.languageVersionOf) is not None:
                continue  # shown with the quote it is a language version of
            text = graph.value(quote, LGO.text)
            quotes.append(
                {
                    "id": name(quote),
                    "lang": text.language if isinstance(text, Literal) else "",
                    "text": str(text),
                    "sourceUrl": one(graph, quote, LGO.sourceUrl),
                    "retrievedOn": one(graph, quote, LGO.retrievedOn),
                    "official": one(graph, quote, LGO.officialLanguageVersion) != "false",
                    "translation": translation_of(graph, quote),
                    "versions": language_versions(graph, quote),
                }
            )
        result.append(
            {
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
                "comments": [t for t in texts(graph, provision, RDFS.comment) if t["lang"] == "en"],
                "document": name(graph.value(provision, LGO.sourceDocument))
                if graph.value(provision, LGO.sourceDocument)
                else None,
                "sourceElement": one(graph, provision, LGO.sourceElement),
                "quotes": quotes,
            }
        )
    return sorted(result, key=lambda p: p["id"])


def concepts(graph: Graph) -> list[dict[str, Any]]:
    result = []
    kinds = {
        LGO.InformationItem: "item",
        LGO.DisclosureType: "disclosure",
        LGO.LegalConcept: "concept",
        LGO.Condition: "condition",
        LGO.Action: "action",
        LGO.ActorRole: "role",
    }
    seen = set()
    for cls, kind in kinds.items():
        for concept in graph.subjects(RDF.type, cls):
            if concept in seen:
                continue
            seen.add(concept)
            result.append(concept_entry(graph, concept, kind))
    for concept in graph.subjects(RDF.type, SKOS.Concept):
        if concept not in seen and str(concept).startswith(str(LGV)):
            result.append(concept_entry(graph, concept, "term"))
    return sorted(result, key=lambda c: (c["kind"], c["label"]))


def concept_entry(graph: Graph, concept: Node, kind: str) -> dict[str, Any]:
    return {
        "id": name(concept),
        "kind": kind,
        "scheme": label(graph, graph.value(concept, SKOS.inScheme)) if graph.value(concept, SKOS.inScheme) else None,
        "label": label(graph, concept),
        "labels": texts(graph, concept, SKOS.prefLabel),
        "altLabels": texts(graph, concept, SKOS.altLabel),
        "definition": next((t["text"] for t in texts(graph, concept, SKOS.definition) if t["lang"] == "en"), None),
        "broader": names(graph, concept, SKOS.broader),
        "narrower": inverse(graph, concept, SKOS.broader),
        "requiredBy": [
            n for n in inverse(graph, concept, LGO.requiresDisclosureOf) if (LG[n], RDF.type, LGO.Provision) in graph
        ],
        "definedBy": inverse(graph, concept, LGO.defines),
        "regulatedBy": inverse(graph, concept, LGO.regulates),
        "enforcedBy": inverse(graph, concept, LGO.enforces),
        "explainedBy": inverse(graph, concept, LGO.explains),
        "question": next((t["text"] for t in texts(graph, concept, LGO.question) if t["lang"] == "en"), None),
        "basedOn": names(graph, concept, LGO.basedOn),
        "holdsWhenAny": names(graph, concept, LGO.holdsWhenAny),
        "holdsWhenAll": names(graph, concept, LGO.holdsWhenAll),
        "usedBy": sorted(
            set(inverse(graph, concept, LGO.appliesWhen))
            | set(inverse(graph, concept, LGO.unless))
            | set(
                n
                for n in inverse(graph, concept, LGO.requiresDisclosureOf)
                if (LG[n], RDF.type, LGO.Obligation) in graph
            )
            | set(inverse(graph, concept, LGO.requiresAction))
            | set(inverse(graph, concept, LGO.bearer))
        ),
    }


def obligations(graph: Graph) -> list[dict[str, Any]]:
    """The rules layer: obligations with their conditions, for the rule pages and the checklist."""
    _, found = rules.load(graph)
    return [
        {
            "id": o.id,
            "label": o.label,
            "comment": o.comment,
            "appliesIn": o.applies_in,
            "appliesWhen": o.applies_when,
            "unless": o.unless,
            "items": o.items,
            "actions": o.actions,
            "disclosure": o.disclosure,
            "establishedBy": o.established_by,
            "refines": o.refines,
            "implementedBy": o.implemented_by,
            "bearer": names(graph, LG[o.id], LGO.bearer),
            "deonticType": name(graph.value(LG[o.id], LGO.deonticType)),
            "reviewStatus": o.status,
            "cases": sorted(
                inverse(graph, LG[o.id], LGO.illustrates),
                key=lambda d: (one(graph, LG[d], ELI.date_document) or "", d),
                reverse=True,
            ),
            # Penalty provisions for a breach of the provisions the rule comes from.
            "penalties": sorted({name(p) for e in o.established_by for p in graph.subjects(LGO.penalises, LG[e])}),
        }
        for o in sorted(found.values(), key=lambda o: o.id)
    ]


def checklist_data(graph: Graph) -> dict[str, Any]:
    """What the checklist page evaluates in the browser: the conditions (asked or derived) and the
    scenarios, with the same rules as `legalgraph checklist`. Where the business is established and
    where it offers its services are jurisdictions: `within` lists those a condition tied to one holds for."""
    conditions, _ = rules.load(graph)
    places = rules.jurisdictions(graph)
    return {
        "conditions": [
            {
                "id": c.id,
                "label": c.label,
                "question": c.question,
                "anyOf": c.any_of,
                "allOf": c.all_of,
                "basedOn": c.based_on,
                "establishedIn": c.established_in,
                "offersIn": c.offered_in,
                "within": sorted(c.within),
            }
            for c in sorted(conditions.values(), key=lambda c: c.id)
        ],
        "jurisdictions": [{"id": j, "label": label} for j, label in sorted(places.items(), key=lambda x: x[1])],
        "markets": sorted({c.offered_in for c in conditions.values() if c.offered_in}),
        "scenarios": [
            {
                "id": s.path.stem,
                "name": s.name,
                "description": s.description,
                "facts": sorted(s.facts),
                "establishedIn": s.established_in,
                "markets": sorted(s.markets),
            }
            for s in rules.load_scenarios()
        ],
    }


def documents(graph: Graph) -> list[dict[str, Any]]:
    result = []
    for document in graph.subjects(RDF.type, LGO.SourceDocument):
        notes = []
        for value in graph.objects(document, LGO.legalStatus):
            if isinstance(value, Literal):
                notes.append(
                    {
                        "text": str(value),
                        "lang": value.language or "",
                        "english": english(graph, document, LGO.legalStatus, value),
                    }
                )
        result.append(
            {
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
                "versionOf": name(graph.value(document, LGO.languageVersionOf))
                if graph.value(document, LGO.languageVersionOf)
                else None,
                "versions": inverse(graph, document, LGO.languageVersionOf),
                "legalStatus": sorted(notes, key=lambda n: n["text"]),
                "licence": label(graph, licence) if (licence := graph.value(document, LGO.licence)) else None,
                "licenceBasis": one(graph, document, LGO.licenceBasis),
            }
        )
    return sorted(result, key=lambda d: d["id"])


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


# --- Writing -------------------------------------------------------------------


def write_json(path: Path, value: Any) -> None:
    # Written next to the target and renamed into place: a running dev server watches these files,
    # and reading one half-written leaves its collection empty until the next change.
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text() == text:
        return
    partial = path.with_name(f".{path.name}.partial")
    partial.write_text(text)
    partial.replace(path)


def resource_turtle(graph: Graph, subject: Node) -> str:
    part = Graph()
    for triple in graph.triples((subject, None, None)):
        part.add(triple)
    return serialize(part, f"<{subject}>\nPart of legalgraph by Aimix GmbH, CC BY 4.0.")


def generate_data(sources: Sources) -> dict[str, int]:
    data, ontology, _, errors = load_all(sources)
    if errors:
        raise SiteError("Turtle syntax errors; run `legalgraph validate`.")
    merged = new_graph()
    merged += data
    merged += ontology

    collections = {
        "jurisdictions": jurisdictions(merged),
        "acts": acts(merged),
        "provisions": provisions(merged),
        "concepts": concepts(merged),
        "documents": documents(merged),
        "obligations": obligations(merged),
    }
    # The reading view of each source document: its annotated sections, line by line. A parallel
    # language version shows the same sections (each provision in both languages). Corrigenda are
    # listed with the document they correct.
    views: dict[str, list[dict[str, Any]]] = {}
    corrigenda: dict[str, list[dict[str, Any]]] = {}
    for source in load_sources():
        sections = reading_view(source)
        for original in source.texts:
            views[repo_path(original.file)] = [s for s in sections if s["source"] == original.file.name]
        for original in source.parallels:
            views[repo_path(original.file)] = sections
        for original in source.texts + source.parallels:
            corrigenda[repo_path(original.file)] = [
                {
                    "role": other.role,
                    "title": other.title or other.file.name,
                    "path": repo_path(other.file),
                    "language": source.language_of(other),
                    "url": other.url,
                    "mediaType": other.media_type,
                    "sha256": other.sha256,
                    "retrievedOn": other.retrieved_on.isoformat(),
                    "corrects": other.corrects,
                }
                for other in source.authentic + source.amendments + source.corrigenda
            ]
    for document in collections["documents"]:
        document["sections"] = views.get(document["path"], [])
        document["related"] = corrigenda.get(document["path"], [])
    for collection, items in collections.items():
        write_json(DATA_DIR / f"{collection}.json", items)
    write_json(DATA_DIR / "graph.json", network(merged))
    write_json(DATA_DIR / "checklist.json", checklist_data(merged))
    counts = {collection: len(items) for collection, items in collections.items()}
    counts["quotes"] = sum(len(p["quotes"]) for p in collections["provisions"])
    counts["translations"] = sum(1 for p in collections["provisions"] for q in p["quotes"] if q["translation"])
    counts["triples"] = len(data)
    write_json(
        DATA_DIR / "meta.json",
        {"counts": counts, "ontologyVersion": one(ontology, URIRef(ONTOLOGY_IRI), OWL.versionInfo)},
    )

    for folder in GENERATED_PUBLIC:
        shutil.rmtree(PUBLIC_DIR / folder, ignore_errors=True)
    citations = {}
    for subject in sorted(set(data.subjects()), key=str):
        if isinstance(subject, URIRef) and str(subject).startswith(str(LG)):
            path = PUBLIC_DIR / "id" / f"{name(subject)}.ttl"
            path.parent.mkdir(parents=True, exist_ok=True)
            turtle = resource_turtle(data, subject)
            path.write_text(turtle)
            citations[name(subject)] = {"iri": str(subject), "sha256": sha256(turtle)}
    for subject in sorted(set(ontology.subjects()), key=str):
        if isinstance(subject, URIRef) and str(subject).startswith(str(LGV)):
            path = PUBLIC_DIR / "vocab" / f"{name(subject)}.ttl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(resource_turtle(ontology, subject))

    downloads = PUBLIC_DIR / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    # For sites that cite the graph (aimix.io): every identifier with a hash of its triples, so a
    # build can check that each cited identifier exists and notice when what it says has changed;
    # and the rules with their conditions, so checklists in articles come from the graph.
    write_json(
        downloads / "citations.json",
        {
            "graphVersion": graph_version(),
            "ontologyVersion": one(ontology, URIRef(ONTOLOGY_IRI), OWL.versionInfo),
            "resources": citations,
        },
    )
    write_json(downloads / "rules.json", {**checklist_data(merged), "obligations": collections["obligations"]})
    (downloads / "legalgraph.ttl").write_text(serialize(data, "legalgraph by Aimix GmbH, CC BY 4.0."))
    data.serialize(destination=downloads / "legalgraph.nt", format="nt", encoding="utf-8")
    data.serialize(destination=downloads / "legalgraph.jsonld", format="json-ld", encoding="utf-8")
    # rdflib's serializer here: the ontology has blank nodes (union ranges) the small writer does not handle.
    ontology.serialize(destination=downloads / "legalgraph-ontology.ttl", format="turtle", encoding="utf-8")

    for source in load_sources():
        for path in [source.index, source.annotated, *(o.file for o in source.originals)]:
            target = PUBLIC_DIR / repo_path(path.resolve())  # sources/<id>/<file>, as in the repository
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    return counts


def graph_version() -> str:
    try:
        return importlib.metadata.version("legalgraph")
    except importlib.metadata.PackageNotFoundError:
        return "0+unknown"


def bun(*args: str) -> None:
    """Run bun in site/, installing dependencies first if needed."""
    if shutil.which("bun") is None:
        raise SiteError("bun not found; install it from https://bun.sh")
    if not (SITE_DIR / "node_modules").exists():
        subprocess.run(["bun", "install", "--frozen-lockfile"], cwd=SITE_DIR, check=True)
    subprocess.run(["bun", *args], cwd=SITE_DIR, check=True)
