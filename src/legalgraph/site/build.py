"""Writing the site's data, its per-resource Turtle, the downloads and the law texts."""

import importlib.metadata
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from rdflib import OWL, Graph, URIRef
from rdflib.term import Node

from legalgraph import LG, LGV
from legalgraph.load import REPO_ROOT, Sources, load_all, new_graph
from legalgraph.localisation import sha256
from legalgraph.site.concepts import checklist_data, concepts, obligations
from legalgraph.site.legislation import acts, documents, jurisdictions
from legalgraph.site.network import network
from legalgraph.site.provisions import provisions
from legalgraph.site.values import name, one
from legalgraph.sources import Original, Source, load_sources, reading_view, repo_path
from legalgraph.turtle import serialize

SITE_DIR = REPO_ROOT / "site"
DATA_DIR = SITE_DIR / "src" / "data"
PUBLIC_DIR = SITE_DIR / "public"
GENERATED_PUBLIC = ("id", "vocab", "downloads", "sources")
ONTOLOGY_IRI = "https://legalgraph.org/ontology"

Collections = dict[str, list[dict[str, Any]]]


class SiteError(Exception):
    pass


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


def related_entry(source: Source, other: Original) -> dict[str, Any]:
    return {
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


def add_reading_views(documents: list[dict[str, Any]]) -> None:
    """The reading view of each source document: its annotated sections, line by line. A parallel
    language version shows the same sections (each provision in both languages). Corrigenda are
    listed with the document they correct."""
    views: Collections = {}
    related: Collections = {}
    for source in load_sources():
        sections = reading_view(source)
        for original in source.texts:
            views[repo_path(original.file)] = [s for s in sections if s["source"] == original.file.name]
        for original in source.parallels:
            views[repo_path(original.file)] = sections
        others = [related_entry(source, other) for other in source.authentic + source.amendments + source.corrigenda]
        for original in source.texts + source.parallels:
            related[repo_path(original.file)] = others
    for document in documents:
        document["sections"] = views.get(document["path"], [])
        document["related"] = related.get(document["path"], [])


def write_collections(merged: Graph, data: Graph, ontology: Graph) -> tuple[Collections, dict[str, int]]:
    collections = {
        "jurisdictions": jurisdictions(merged),
        "acts": acts(merged),
        "provisions": provisions(merged),
        "concepts": concepts(merged),
        "documents": documents(merged),
        "obligations": obligations(merged),
    }
    add_reading_views(collections["documents"])
    for collection, items in collections.items():
        write_json(DATA_DIR / f"{collection}.json", items)
    write_json(DATA_DIR / "graph.json", network(merged))
    write_json(DATA_DIR / "checklist.json", checklist_data(merged))
    counts = {collection: len(items) for collection, items in collections.items()}
    counts["quotes"] = sum(len(p["quotes"]) for p in collections["provisions"])
    counts["translations"] = sum(1 for p in collections["provisions"] for q in p["quotes"] if q["translation"])
    counts["triples"] = len(data)
    write_json(DATA_DIR / "meta.json", {"counts": counts, "ontologyVersion": ontology_version(ontology)})
    return collections, counts


def write_resources(data: Graph, ontology: Graph) -> dict[str, dict[str, str]]:
    """Each lg: resource and lgv: term as its own Turtle file; the citations of the lg: ones."""
    for folder in GENERATED_PUBLIC:
        shutil.rmtree(PUBLIC_DIR / folder, ignore_errors=True)
    citations = {}
    for subject in sorted(set(data.subjects()), key=str):
        if isinstance(subject, URIRef) and str(subject).startswith(str(LG)):
            turtle = resource_turtle(data, subject)
            write_text(PUBLIC_DIR / "id" / f"{name(subject)}.ttl", turtle)
            citations[name(subject)] = {"iri": str(subject), "sha256": sha256(turtle)}
    for subject in sorted(set(ontology.subjects()), key=str):
        if isinstance(subject, URIRef) and str(subject).startswith(str(LGV)):
            write_text(PUBLIC_DIR / "vocab" / f"{name(subject)}.ttl", resource_turtle(ontology, subject))
    return citations


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_downloads(merged: Graph, data: Graph, ontology: Graph, citations: dict, obligations: list) -> None:
    downloads = PUBLIC_DIR / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    # For sites that cite the graph (aimix.io): every identifier with a hash of its triples, so a
    # build can check that each cited identifier exists and notice when what it says has changed;
    # and the rules with their conditions, so checklists in articles come from the graph.
    write_json(
        downloads / "citations.json",
        {"graphVersion": graph_version(), "ontologyVersion": ontology_version(ontology), "resources": citations},
    )
    write_json(downloads / "rules.json", {**checklist_data(merged), "obligations": obligations})
    (downloads / "legalgraph.ttl").write_text(serialize(data, "legalgraph by Aimix GmbH, CC BY 4.0."))
    data.serialize(destination=downloads / "legalgraph.nt", format="nt", encoding="utf-8")
    data.serialize(destination=downloads / "legalgraph.jsonld", format="json-ld", encoding="utf-8")
    # rdflib's serializer here: the ontology has blank nodes (union ranges) the small writer does not handle.
    ontology.serialize(destination=downloads / "legalgraph-ontology.ttl", format="turtle", encoding="utf-8")


def copy_sources() -> None:
    """The law texts and their indexes, at sources/<id>/<file> as in the repository."""
    for source in load_sources():
        for path in [source.index, source.annotated, *(o.file for o in source.originals)]:
            target = PUBLIC_DIR / repo_path(path.resolve())
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


def generate_data(sources: Sources) -> dict[str, int]:
    data, ontology, _, errors = load_all(sources)
    if errors:
        raise SiteError("Turtle syntax errors; run `legalgraph validate`.")
    merged = new_graph()
    merged += data
    merged += ontology
    collections, counts = write_collections(merged, data, ontology)
    citations = write_resources(data, ontology)
    write_downloads(merged, data, ontology, citations, collections["obligations"])
    copy_sources()
    return counts


def ontology_version(ontology: Graph) -> str | None:
    return one(ontology, URIRef(ONTOLOGY_IRI), OWL.versionInfo)


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
