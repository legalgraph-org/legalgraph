"""Guidance that may be read but not republished: a regulator's guide whose terms do not let us keep
and redistribute it. The graph keeps what it concludes, point by point, in our own words, with where
each point is found and the provisions it interprets; readers follow the link to the original.

The original itself is downloaded only into sources/.local/ (git-ignored), so maintainers can check
the findings against it; its SHA-256 records which version was read."""

import datetime as dt
import re

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field
from rdflib import RDF, RDFS, XSD, Graph, Literal
from rdflib.term import Node

from legalgraph import ELI, LG, LGO, LGV
from legalgraph.sources.constants import SOURCES_DIR

LOCAL_DIR = SOURCES_DIR / ".local"  # git-ignored: originals kept for checking, never published


def page_words(data: bytes) -> str | None:
    """The visible words of an HTML page (None for anything else): web pages change their markup on
    every request, so a page counts as the version read when its words are the same."""
    if not data.lstrip()[:200].lower().startswith((b"<!doctype html", b"<html")):
        return None
    soup = BeautifulSoup(data, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def same_version(read: bytes, served: bytes) -> bool:
    """The publisher still serves the version that was read: the same bytes, or the same words."""
    words = page_words(read)
    return read == served or (words is not None and words == page_words(served))


class LocalCopy(BaseModel):
    """The original as read, kept outside the repository: sources/.local/<entry id>/<file>."""

    model_config = ConfigDict(extra="forbid")

    url: str
    file: str = Field(pattern=r"^[^/\\]+$")
    retrieved_on: dt.date
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Finding(BaseModel):
    """One point the guidance makes, stated in our words (English), never quoted."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Z]{2}-[A-Za-z0-9-]+$")
    locator: str
    finding: str
    interprets: list[str] = Field(default_factory=list)
    regulates: list[str] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)


class GuidanceDocument(BaseModel):
    """What makes a link-only entry a guidance document of its own in the graph."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Z]{2}-[A-Z0-9-]+$")
    short_name: str
    jurisdiction: str = Field(pattern=r"^[A-Z]{2,3}$")
    language: str
    title_en: str | None = None
    findings: list[Finding] = Field(min_length=1)


def add_guidance(
    graph: Graph,
    node: Node,
    document: GuidanceDocument,
    title: str,
    url: str,
    date: dt.date | None,
) -> None:
    """The guidance as a lgo:Guidance that is also a link-only reference, and each finding as a
    provision of it: citation and link, our statement of the point, and what it interprets."""
    graph.add((node, RDF.type, LGO.Guidance))
    graph.add((node, ELI.title, Literal(title, lang=document.language)))
    if document.title_en:
        graph.add((node, ELI.title, Literal(document.title_en, lang="en")))
    graph.add((node, LGO.shortName, Literal(document.short_name)))
    graph.add((node, LGO.actType, LGV.Guidelines))
    graph.add((node, LGO.jurisdiction, LG[document.jurisdiction]))
    graph.add((node, LGO.reviewStatus, LGV.Draft))
    if date:
        graph.add((node, ELI.date_document, Literal(date.isoformat(), datatype=XSD.date)))
    for finding in document.findings:
        point = LG[finding.id]
        graph.add((point, RDF.type, LGO.Provision))
        graph.add((point, ELI.is_part_of, node))
        graph.add((point, LGO.citation, Literal(f"{document.short_name}, {finding.locator}")))
        graph.add((point, LGO.sourceUrl, Literal(url, datatype=XSD.anyURI)))
        graph.add((point, RDFS.comment, Literal(finding.finding, lang="en")))
        graph.add((point, LGO.reviewStatus, LGV.Draft))
        for target in finding.interprets:
            graph.add((point, LGO.interprets, LG[target]))
        for concept in finding.regulates:
            graph.add((point, LGO.regulates, LGV[concept]))
        for item in finding.requires:
            graph.add((point, LGO.requiresDisclosureOf, LGV[item]))
