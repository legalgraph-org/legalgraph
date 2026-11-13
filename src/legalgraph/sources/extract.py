"""extract: Turtle generated mechanically from an annotated XML. Same input, same bytes.

The act, its source documents, each annotated provision with its quote, the same provision in every
parallel language version, and the cross-references inside an EU act.
"""

import re
import xml.etree.ElementTree as ET

from rdflib import DCTERMS, RDF, XSD, Graph, Literal, URIRef

from legalgraph import ELI, LG, LGO, LGV
from legalgraph.sources.constants import DOCUMENT_CLASSES, LICENCES, LINK_PREDICATES, PROVISION_ROLES, ROLE_PREDICATES
from legalgraph.sources.metadata import act_metadata
from legalgraph.sources.model import Original, Source, SourceError, repo_path
from legalgraph.sources.references import internal_references
from legalgraph.sources.render import render
from legalgraph.sources.tree import (
    annotation,
    element_at,
    inside_provision,
    local,
    parents_of,
    provision_named,
    required,
    section_source,
    xpath,
)
from legalgraph.turtle import serialize


def decision_identifier(root: ET.Element) -> str | None:
    """The European Case Law Identifier of a Formex judgment."""
    ecli = root.find("BIB.JUDGMENT/NO.ECLI")
    return ecli.get("ECLI") if ecli is not None else None


def date_literal(value: str) -> Literal:
    return Literal(value, datatype=XSD.date)


class Extraction:
    """The triples of one source, added part by part to one graph."""

    def __init__(self, source: Source) -> None:
        self.source = source
        self.root = ET.fromstring(source.annotated.read_bytes())
        self.parents = parents_of(self.root)
        self.graph = Graph()
        self.where = repo_path(source.annotated)
        self.act = LG[required(self.root, "act", self.where)]
        # A parallel's text is the file itself for official XML, or its own authored XML for a
        # translation written in schemas/law.xsd (`annotated` on the original).
        self.parallel_roots = {
            original.file.name: ET.fromstring((original.annotated or original.file).read_bytes())
            for original in source.parallels
        }
        self.parallel_parents = {name: parents_of(tree) for name, tree in self.parallel_roots.items()}
        self.documents = self.document_names()

    def add(self, subject: URIRef, predicate: URIRef, value: URIRef | Literal) -> None:
        self.graph.add((subject, predicate, value))

    def document_names(self) -> dict[str, URIRef]:
        source = self.source
        base = source.document or f"{self.act.removeprefix(str(LG))}-source"
        documents = {
            original.file.name: LG[base if len(source.texts) == 1 else f"{base}-{number}"]
            for number, original in enumerate(source.texts, 1)
        }
        for original in source.parallels:
            documents[original.file.name] = LG[f"{base}-{source.language_of(original)}"]
        for number, original in enumerate(self.verifying(), 1):
            documents[original.file.name] = LG[f"{base}-official" + (f"-{number}" if number > 1 else "")]
        return documents

    def verifying(self) -> list[Original]:
        """The authentic originals a mirror's text was checked against (authored sources; an EU
        consolidation's authentic texts are checked too, but its own text is the official one)."""
        if self.source.kind != "authored-xml" or all(o.official for o in self.source.texts):
            return []
        return [o for o in self.source.authentic if self.source.language_of(o) == self.source.language]

    def authenticity(self, document: URIRef, original: Original) -> None:
        if original.official or original.role == "authentic":
            self.add(document, LGO.authenticity, LGV.Official)
            return
        verified = [self.documents[o.file.name] for o in self.verifying()] if original.role == "text" else []
        self.add(document, LGO.authenticity, LGV.VerifiedAgainstOfficial if verified else LGV.NotVerified)
        for official in verified:
            self.add(document, LGO.verifiedAgainst, official)

    def source_document(self, original: Original, notes: list[str]) -> None:
        source, document = self.source, self.documents[original.file.name]
        self.add(document, RDF.type, LGO.SourceDocument)
        self.add(document, DCTERMS.language, Literal(source.language_of(original), datatype=XSD.language))
        self.add(document, LGO.repositoryPath, Literal(repo_path(original.file)))
        if original.role == "text":
            self.add(document, LGO.annotatedFile, Literal(self.where))
        self.add(document, LGO.mediaType, Literal(original.media_type))
        self.add(document, LGO.sha256, Literal(original.sha256))
        self.add(document, LGO.sourceUrl, Literal(original.url, datatype=XSD.anyURI))
        self.add(document, LGO.retrievedOn, date_literal(original.retrieved_on.isoformat()))
        for note in notes:
            self.add(document, LGO.legalStatus, Literal(note, lang=source.language))
        for note in original.notes:
            self.add(document, LGO.legalStatus, Literal(note, lang="en"))
        if source.licence:
            self.add(document, LGO.licence, LICENCES[source.licence])
            self.add(document, LGO.licenceBasis, Literal(source.licence_basis))
        if builddate := self.root.get("builddate"):
            self.add(document, LGO.portalBuildDate, Literal(builddate))
        if original.role == "parallel":
            self.add(document, LGO.languageVersionOf, self.documents[source.texts[0].file.name])
        self.authenticity(document, original)

    def act_triples(self, title: str | None, short: str | None, issued: str | None) -> None:
        act, root, where = self.act, self.root, self.where
        act_type = required(root, "act-type", where)
        self.add(act, RDF.type, DOCUMENT_CLASSES.get(act_type, LGO.LegalAct))
        if ecli := decision_identifier(root):
            self.add(act, LGO.ecli, Literal(ecli))
        self.add(act, LGO.jurisdiction, LG[required(root, "jurisdiction", where)])
        self.add(act, LGO.actType, LGV[act_type])
        self.add(act, LGO.sourceUrl, Literal(required(root, "url", where), datatype=XSD.anyURI))
        self.add(act, LGO.reviewStatus, LGV.SourceChecked)
        for document in self.documents.values():
            self.add(act, LGO.sourceDocument, document)
        for target in (annotation(root, "transposes") or "").split():
            self.add(act, ELI.transposes, LG[target])
        if title:
            self.add(act, ELI.title, Literal(title, lang=self.source.language))
        if short:
            self.add(act, LGO.shortName, Literal(short))
        if issued:
            self.add(act, ELI.date_document, date_literal(issued))

    def check_items_inside_provisions(self) -> None:
        for element in self.root.iter():
            if annotation(element, "requires") and not inside_provision(element, self.parents):
                raise SourceError(f"{self.where}: {xpath(element, self.parents)} has lga:requires outside a provision")

    def provision_links(self, provision: URIRef, element: ET.Element) -> None:
        for role, (namespace, predicate) in (ROLE_PREDICATES | LINK_PREDICATES).items():
            for target in (annotation(element, role) or "").split():
                self.add(provision, predicate, namespace[target])
        for item in element.iter():
            for concept in (annotation(item, "requires") or "").split():
                self.add(provision, LGO.requiresDisclosureOf, LGV[concept])
            if item is not element:
                for concept in (annotation(item, "defines") or "").split():
                    self.add(provision, LGO.defines, LGV[concept])

    def provision(self, element: ET.Element) -> None:
        source, where = self.source, self.where
        provision = LG[required(element, "provision", where)]
        if not any(annotation(node, role) for node in element.iter() for role in PROVISION_ROLES):
            raise SourceError(f"{where}: {provision} needs one of lga:{', lga:'.join(PROVISION_ROLES)}")
        file_name = section_source(element, self.parents) if len(source.texts) > 1 else source.texts[0].file.name
        original = source.original(file_name)
        document = self.documents[file_name]
        # A provision without a page of its own (EUR-Lex has none per article) links to the act.
        url = Literal(
            annotation(element, "url") or original.page or required(self.root, "url", where), datatype=XSD.anyURI
        )
        path = Literal(xpath(element, self.parents))
        self.add(provision, RDF.type, LGO.Provision)
        self.add(provision, ELI.is_part_of, self.act)
        self.add(provision, LGO.citation, Literal(required(element, "citation", where)))
        for predicate, value in ((LGO.sourceUrl, url), (LGO.sourceDocument, document), (LGO.sourceElement, path)):
            self.add(provision, predicate, value)
        self.add(provision, LGO.reviewStatus, LGV.SourceChecked)
        self.provision_links(provision, element)

        quote = LG[f"{provision.removeprefix(str(LG))}-q1"]
        self.add(quote, RDF.type, LGO.Quote)
        self.add(quote, LGO.quoteOf, provision)
        self.add(quote, LGO.text, Literal(render(element), lang=source.language))
        self.add(quote, LGO.sourceUrl, url)
        self.add(quote, LGO.retrievedOn, date_literal(original.retrieved_on.isoformat()))
        self.add(quote, LGO.officialLanguageVersion, Literal(original.authentic))
        self.add(quote, LGO.sourceDocument, document)
        self.add(quote, LGO.sourceElement, path)
        for parallel in source.parallels:
            self.language_version(element, provision, quote, parallel, url)

    def parallel_match(
        self, element: ET.Element, parallel: Original, url: Literal
    ) -> tuple[ET.Element, str, str] | None:
        """The same provision in a parallel text, with its URL and path: matched by position for
        official XML, by lga:provision for an authored translation."""
        tree = self.parallel_roots[parallel.file.name]
        if parallel.annotated is not None:
            match = provision_named(tree, annotation(element, "provision"))
            if match is None:
                return None  # no official version in this language: a translation is required instead
            return (
                match,
                annotation(match, "url") or parallel.page or url,
                xpath(match, self.parallel_parents[parallel.file.name]),
            )
        path = xpath(element, self.parents)
        match = element_at(tree, path)
        if match is None:
            raise SourceError(f"{parallel.file.name}: no element at {path}; run `legalgraph sources verify`")
        return match, annotation(element, "url") or parallel.page or url, path

    def language_version(
        self, element: ET.Element, provision: URIRef, quote: URIRef, parallel: Original, url: Literal
    ) -> None:
        found = self.parallel_match(element, parallel, url)
        if found is None:
            return
        match, version_url, version_path = found
        language = self.source.language_of(parallel)
        version = LG[f"{quote.removeprefix(str(LG))}-{language}"]
        self.add(version, RDF.type, LGO.Quote)
        self.add(version, LGO.quoteOf, provision)
        self.add(version, LGO.languageVersionOf, quote)
        self.add(version, LGO.text, Literal(render(match), lang=language))
        self.add(version, LGO.sourceUrl, Literal(version_url, datatype=XSD.anyURI))
        self.add(version, LGO.retrievedOn, date_literal(parallel.retrieved_on.isoformat()))
        self.add(version, LGO.officialLanguageVersion, Literal(parallel.authentic))
        self.add(version, LGO.sourceDocument, self.documents[parallel.file.name])
        self.add(version, LGO.sourceElement, Literal(version_path))

    def cross_references(self) -> None:
        if local(self.root.tag) not in ("ACT", "CONS.ACT") or self.source.language != "en":
            return
        provisions = {str(s) for s in self.graph.subjects(RDF.type, LGO.Provision)}
        for provision in sorted(provisions):
            quote = self.graph.value(URIRef(f"{provision}-q1"), LGO.text)
            own = re.search(r"-art(\d+)", provision)
            for target in internal_references(str(quote), str(self.act), own.group(1) if own else None):
                if target != provision and target in provisions:
                    self.add(URIRef(provision), LGO.refersTo, URIRef(target))

    def run(self) -> Graph:
        metadata = act_metadata(self.root)
        for original in self.source.texts + self.source.parallels + self.verifying():
            self.source_document(original, metadata.notes)
        self.act_triples(metadata.title, metadata.short, metadata.issued)
        self.check_items_inside_provisions()
        for element in self.root.iter():
            if element is not self.root and annotation(element, "provision"):
                self.provision(element)
        self.cross_references()
        return self.graph


def extract(source: Source) -> str:
    extraction = Extraction(source)
    comment = (
        f"Generated by `legalgraph sources extract` from {extraction.where}. Do not edit:\n"
        "change the annotations in the source and run the command again."
    )
    return serialize(extraction.run(), comment)
