"""English localisation: find what is not yet in English, export it as a worklist, apply translations.

Two kinds of text need English, and both are translated through lgo:Translation nodes in
data/translations/en/<jurisdiction>.ttl, with provenance and a SHA-256 of the source text:

- quotes (lgo:Quote lgo:text in another language): the translation is `<quote>-en` and goes stale
  when the quote changes. A quote that is a language version of an English quote (lgo:languageVersionOf,
  e.g. the German text of an EU regulation) needs none: the English is equally official;
- short literals on properties marked lgo:englishRequired (titles, labels, status notes): the
  translation names the property (lgo:translatedProperty) and carries the hash of the value it
  translates, so a changed value is reported as missing and the old translation as orphaned.
  A hand-written @en literal on the same subject and property also counts as English.

The worklist is plain JSON, so any translator (a language model in CI, a person) can fill it in.
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from rdflib import RDF, XSD, Graph, Literal, URIRef
from rdflib.term import Node

from legalgraph import LG, LGO, LGV
from legalgraph.turtle import serialize

TRANSLATIONS_SUBDIR = Path("translations") / "en"
METHODS = {"machine": LGV.MachineTranslation, "human": LGV.HumanTranslation, "official": LGV.OfficialTranslation}
HEADER = """English translations. Managed by `legalgraph translations apply`.
To review one: correct lgo:text if needed, add lgo:reviewedBy and set lgo:reviewStatus lgv:Reviewed."""


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def local_name(iri: str) -> str:
    return iri.rstrip("/#").replace("#", "/").rsplit("/", 1)[-1]


def translation_iri(subject: str, predicate: str | None = None, digest: str | None = None) -> URIRef:
    """`<quote>-en` for a quote; `<subject>-<property>-<hash prefix>-en` for a literal."""
    if predicate is None:
        return URIRef(f"{subject}-en")
    return URIRef(f"{subject}-{local_name(predicate)}-{digest[:12] if digest else ''}-en")


def jurisdiction_of(resource: str) -> str:
    """lg:DE-DDG-s5-1-q1 -> "de": the translation file the resource belongs in."""
    return resource.removeprefix(str(LG)).split("-", 1)[0].lower()


@dataclass
class WorkItem:
    kind: str  # "quote" or "literal"
    subject: str
    lang: str
    text: str
    sha256: str
    reason: str  # "missing" or "stale"
    predicate: str | None = None
    translation: str | None = None


def official_english(data: Graph, quote: Node) -> bool:
    """The quote has an English language version published by the same institution (an EU act, the
    English text of Swiss federal law): that is its English, with its own authenticity flag, rather than
    a translation of ours."""
    others = [*data.objects(quote, LGO.languageVersionOf), *data.subjects(LGO.languageVersionOf, quote)]
    for other in others:
        text = data.value(other, LGO.text)
        if isinstance(text, Literal) and text.language == "en":
            return True
    return False


def pending_quotes(data: Graph) -> list[WorkItem]:
    items = []
    for quote in sorted(data.subjects(RDF.type, LGO.Quote), key=str):
        text = data.value(quote, LGO.text)
        if not isinstance(text, Literal) or text.language in (None, "en") or official_english(data, quote):
            continue
        digest = sha256(str(text))
        existing = translation_iri(str(quote))
        if (existing, RDF.type, LGO.Translation) not in data:
            reason = "missing"
        elif str(data.value(existing, LGO.sourceTextSha256)) != digest:
            reason = "stale"
        else:
            continue
        items.append(WorkItem("quote", str(quote), str(text.language), str(text), digest, reason))
    return items


def pending_literals(data: Graph, ontology: Graph) -> list[WorkItem]:
    required = set(ontology.subjects(LGO.englishRequired, Literal(True)))
    items = []
    for subject, predicate, value in sorted(data, key=lambda triple: tuple(map(str, triple))):
        if predicate not in required or not isinstance(value, Literal) or value.language in (None, "en"):
            continue
        curated = any(isinstance(o, Literal) and o.language == "en" for o in data.objects(subject, predicate))
        digest = sha256(str(value))
        if curated or (translation_iri(str(subject), str(predicate), digest), RDF.type, LGO.Translation) in data:
            continue
        items.append(
            WorkItem("literal", str(subject), str(value.language), str(value), digest, "missing", str(predicate))
        )
    return items


def orphans(data: Graph) -> list[str]:
    """Literal translations whose source value is no longer in the graph: delete them."""
    found = []
    for node in data.subjects(LGO.translatedProperty, None):
        subject, predicate = data.value(node, LGO.translationOf), data.value(node, LGO.translatedProperty)
        digest = str(data.value(node, LGO.sourceTextSha256))
        if not any(sha256(str(value)) == digest for value in data.objects(subject, predicate)):
            found.append(f"{data.qname(node)}: translates a value that is no longer in the graph; delete it")
    return sorted(found)


def line_mismatches(data: Graph) -> list[str]:
    """Quote translations must keep the quote's lines (one per paragraph or numbered item), so readers
    can compare them line by line."""
    found = []
    for node in data.subjects(RDF.type, LGO.Translation):
        quote = data.value(node, LGO.translationOf)
        if data.value(node, LGO.translatedProperty) is not None or (quote, RDF.type, LGO.Quote) not in data:
            continue
        source = str(data.value(quote, LGO.text)).splitlines()
        english = str(data.value(node, LGO.text)).splitlines()
        if len(source) != len(english):
            found.append(
                f"{data.qname(node)}: {len(english)} lines, but the quote has {len(source)}; "
                "keep one line per paragraph or numbered item"
            )
    return sorted(found)


def pending(data: Graph, ontology: Graph) -> list[WorkItem]:
    return pending_quotes(data) + pending_literals(data, ontology)


def describe(item: WorkItem, graph: Graph) -> str:
    what = graph.qname(URIRef(item.subject))
    if item.predicate:
        what += f" {graph.qname(URIRef(item.predicate))}"
    return f"{what}: {item.reason} English translation of @{item.lang} text"


def write_worklist(items: list[WorkItem], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2) + "\n")


def read_worklist(path: Path) -> list[WorkItem]:
    return [WorkItem(**entry) for entry in json.loads(path.read_text())]


def apply(data_dir: Path, items: list[WorkItem], translated_by: str, method: str, on: date) -> list[Path]:
    """Merge filled-in work items into the tool-managed translation files. New translations are Draft."""
    directory = data_dir / TRANSLATIONS_SUBDIR
    translations = Graph()
    for path in sorted(directory.glob("*.ttl")):
        translations.parse(path, format="turtle")

    for item in items:
        if not item.translation:
            continue
        node = translation_iri(item.subject, item.predicate, item.sha256)
        translations.remove((node, None, None))
        translations.add((node, RDF.type, LGO.Translation))
        translations.add((node, LGO.translationOf, URIRef(item.subject)))
        if item.predicate:
            translations.add((node, LGO.translatedProperty, URIRef(item.predicate)))
        translations.add((node, LGO.text, Literal(item.translation, lang="en")))
        translations.add((node, LGO.translationMethod, METHODS[method]))
        translations.add((node, LGO.translatedBy, Literal(translated_by)))
        translations.add((node, LGO.translatedOn, Literal(on.isoformat(), datatype=XSD.date)))
        translations.add((node, LGO.sourceTextSha256, Literal(item.sha256)))
        translations.add((node, LGO.reviewStatus, LGV.Draft))

    by_file: dict[str, Graph] = {}
    for node in translations.subjects(RDF.type, LGO.Translation):
        part = by_file.setdefault(jurisdiction_of(str(node)), Graph())
        for triple in translations.triples((node, None, None)):
            part.add(triple)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, part in sorted(by_file.items()):
        path = directory / f"{name}.ttl"
        path.write_text(serialize(part, HEADER))
        written.append(path)
    return written
