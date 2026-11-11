"""Official law texts as the starting point of the graph: download, verify, extract.

Each directory under sources/ holds one act and a source.yaml index that says where every file comes
from. The ETL is:

1. fetch: download the originals exactly as the index describes (a file from a zip, an HTML
   fragment cut out by a CSS selector, or a file as served). `fetch --check` downloads again and
   compares SHA-256s, so a scheduled job can prove the committed texts still match the portals.
2. annotate: one annotated XML per act.
   - official-xml: a copy of the official XML with lga: attributes added. `verify` proves that
     removing them gives back the original byte for byte.
   - authored-xml: when the portal has no XML, the maintainers write the text in the schema
     schemas/law.xsd. `verify` validates it and proves every paragraph's text occurs word for word
     in the downloaded original.
3. extract: Turtle generated mechanically from the annotated XML. Same input, same bytes.

Three XML dialects are read: gesetze-im-internet.de (German federal law), Formex 4 (the EU
Official Journal) and our own schema. An official-xml source can list other official language
versions of the same text (role: parallel, e.g. the German GDPR next to the English one): they are
not annotated, but must have the same structure, and each provision's text in them becomes a quote
in that language. An authored-xml source can list an official translation as a parallel too, but
then the parallel's text is a second file written in schemas/law.xsd (named by its `annotated`),
matched to the provisions by lga:provision; `as_of` is the translation's date, and an amendment note
in the original newer than that makes verify fail. Corrigenda published for the text are kept too
(role: corrigendum), with the places they correct, and `verify` fails if one corrects an annotated
provision.
"""

import copy
import functools
import gzip
import hashlib
import io
import logging
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import xml.parsers.expat
import xml.sax.saxutils
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from bs4 import BeautifulSoup
from lxml import etree
from pypdf import PdfReader
from rdflib import DCTERMS, RDF, RDFS, XSD, Graph, Literal, URIRef

from legalgraph import ELI, LG, LGO, LGV
from legalgraph.load import REPO_ROOT
from legalgraph.turtle import serialize

# pypdf logs notices about some PDFs' font encodings; the text check does not depend on them.
logging.getLogger("pypdf").setLevel(logging.CRITICAL)

ANNOTATION_NS = "https://legalgraph.org/ns/annotation#"
LAW_NS = "https://legalgraph.org/ns/law#"
CLML_NS = "http://www.legislation.gov.uk/namespaces/legislation"
AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
SOURCES_DIR = REPO_ROOT / "sources"
EXTRACTED_DIR = REPO_ROOT / "data" / "extracted"
LAW_SCHEMA = REPO_ROOT / "schemas" / "law.xsd"
USER_AGENT = "legalgraph (+https://legalgraph.org)"

ROOT_ATTRIBUTES = {"act", "jurisdiction", "act-type", "transposes", "url"}
# Annotation → (namespace of its values, predicate). The first group are the roles a provision needs
# at least one of; the second relate it to provisions elsewhere.
ROLE_PREDICATES = {
    "regulates": (LGV, LGO.regulates),
    "enforces": (LGV, LGO.enforces),
    "defines": (LGV, LGO.defines),
    "authorises": (LG, LGO.authorises),
    "explains": (LGV, LGO.explains),
    "interprets": (LG, LGO.interprets),
    "specifies": (LG, LGO.specifies),
    "applies": (LG, LGO.applies),
    "penalises": (LG, LGO.penalises),
}
LINK_PREDICATES = {
    "implements": (LG, LGO.implements),
    "takes-precedence-over": (LG, LGO.takesPrecedenceOver),
    "refers-to": (LG, LGO.refersTo),
    "proposes-to-amend": (LG, LGO.proposesToAmend),
}
PROVISION_ROLES = tuple(ROLE_PREDICATES)
PROVISION_ATTRIBUTES = {"provision", "citation", "url", "requires", *ROLE_PREDICATES, *LINK_PREDICATES}
# The kind of document the root's lga:act-type makes it: legislation, a court decision or guidance.
DOCUMENT_CLASSES = {
    "Judgment": LGO.CourtDecision,
    "Guidelines": LGO.Guidance,
    "AuthorityDecision": LGO.AuthorityDecision,
}
ITEM_ATTRIBUTES = {"requires", "defines"}
KINDS = {"official-xml", "authored-xml"}
FETCH_METHODS = {"zip-member", "html-fragment", "file"}
ROLES = {"text", "parallel", "authentic", "amendment", "corrigendum"}
# On what terms an original may be kept and republished (source.yaml `licence`, vocab/licences.ttl).
# Someone else's writing that none of these covers is not kept: it goes into sources/link-only.yaml.
LICENCES = {
    "public-domain": LGV.PublicDomain,
    "official-work": LGV.OfficialWork,
    "licence-ouverte-2.0": LGV.LicenceOuverte2,
    "ogl-3.0": LGV.OpenGovernmentLicence3,
    "reuse-with-attribution": LGV.ReuseWithAttribution,
}
LINK_ONLY = SOURCES_DIR / "link-only.yaml"
LINK_ONLY_OUTPUT = EXTRACTED_DIR / "link-only.ttl"
EXCERPT_LIMIT = 300  # characters: one or two sentences of someone else's work, never more

# Removing these from an annotated official XML must give back the original bytes.
STRIP_PATTERNS = [
    re.compile(rb' xmlns:lga="' + re.escape(ANNOTATION_NS.encode()) + rb'"'),
    re.compile(rb' lga:[A-Za-z][A-Za-z-]*="[^"]*"'),
]


class SourceError(Exception):
    pass


@dataclass
class Original:
    file: Path
    url: str
    fetch: str
    media_type: str
    retrieved_on: date
    sha256: str
    member: str | None = None
    selector: str | None = None
    text_ignore: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    role: str = "text"
    language: str | None = None
    title: str | None = None
    corrects: list[str] = field(default_factory=list)
    page: str | None = None
    notes: list[str] = field(default_factory=list)
    authentic: bool = True  # False for a translation published for information (a judgment outside its case language)
    pause: float = 0  # seconds to wait before downloading, for portals that block quick successive requests
    annotated: Path | None = None  # authored-xml parallel: its own XML written in schemas/law.xsd
    as_of: date | None = None  # the translation's date: amendment notes newer than this make it stale


@dataclass
class Source:
    index: Path
    id: str
    title: str
    jurisdiction: str
    language: str
    kind: str
    originals: list[Original]
    annotated: Path
    document: str | None = None  # identifier of the source document, when <act>-source is taken
    licence: str | None = None  # a key of LICENCES
    licence_basis: str | None = None  # why it applies

    @property
    def directory(self) -> Path:
        return self.index.parent

    @property
    def output(self) -> Path:
        return EXTRACTED_DIR / f"{self.id}.ttl"

    @property
    def texts(self) -> list[Original]:
        return [original for original in self.originals if original.role == "text"]

    @property
    def parallels(self) -> list[Original]:
        return [original for original in self.originals if original.role == "parallel"]

    @property
    def corrigenda(self) -> list[Original]:
        return [original for original in self.originals if original.role == "corrigendum"]

    @property
    def authentic(self) -> list[Original]:
        return [original for original in self.originals if original.role == "authentic"]

    @property
    def amendments(self) -> list[Original]:
        return [original for original in self.originals if original.role == "amendment"]

    def language_of(self, original: Original) -> str:
        return original.language or self.language

    def original(self, name: str) -> Original:
        for original in self.originals:
            if original.file.name == name:
                return original
        raise SourceError(f"{repo_path(self.index)}: no original named {name!r}")


# --- Index -------------------------------------------------------------------


def parse_index(index: Path) -> Source:
    config = yaml.safe_load(index.read_text())
    where = repo_path(index)
    try:
        kind = config["kind"]
        if kind not in KINDS:
            raise SourceError(f"{where}: kind must be one of {sorted(KINDS)}")
        licence = config.get("licence")
        if licence is not None and licence not in LICENCES:
            raise SourceError(f"{where}: licence must be one of {sorted(LICENCES)}")
        if licence is not None and not config.get("licence_basis"):
            raise SourceError(f"{where}: give `licence_basis` with `licence`")
        originals = []
        for entry in config["originals"]:
            if entry["fetch"] not in FETCH_METHODS:
                raise SourceError(f"{where}: fetch must be one of {sorted(FETCH_METHODS)}")
            if entry.get("role", "text") not in ROLES:
                raise SourceError(f"{where}: role must be one of {sorted(ROLES)}")
            if (entry.get("annotated") or entry.get("as_of")) and entry.get("role", "text") != "parallel":
                raise SourceError(f"{where}: `annotated` and `as_of` are for parallel language versions")
            originals.append(
                Original(
                    file=(index.parent / entry["file"]).resolve(),
                    url=entry["url"],
                    fetch=entry["fetch"],
                    media_type=entry["media_type"],
                    retrieved_on=entry["retrieved_on"],
                    sha256=str(entry["sha256"]),
                    member=entry.get("member"),
                    selector=entry.get("selector"),
                    text_ignore=entry.get("text_ignore", []),
                    headers=entry.get("headers", {}),
                    role=entry.get("role", "text"),
                    language=entry.get("language"),
                    title=entry.get("title"),
                    corrects=entry.get("corrects", entry.get("amends", [])),
                    page=entry.get("page"),
                    notes=entry.get("notes", []),
                    authentic=entry.get("authentic", True),
                    pause=float(entry.get("pause", 0)),
                    annotated=(index.parent / entry["annotated"]).resolve() if entry.get("annotated") else None,
                    as_of=entry.get("as_of"),
                )
            )
        return Source(
            index=index,
            id=config["id"],
            title=config["title"],
            jurisdiction=config["jurisdiction"],
            language=config["language"],
            kind=kind,
            originals=originals,
            annotated=index.parent / config["annotated"],
            document=config.get("document"),
            licence=licence,
            licence_basis=config.get("licence_basis"),
        )
    except KeyError as error:
        raise SourceError(f"{where}: missing field {error}") from error


def load_sources(root: Path = SOURCES_DIR, ids: tuple[str, ...] = ()) -> list[Source]:
    sources = [parse_index(index) for index in sorted(root.rglob("source.yaml"))]
    if ids:
        unknown = set(ids) - {source.id for source in sources}
        if unknown:
            raise SourceError(f"Unknown source(s): {', '.join(sorted(unknown))}")
        sources = [source for source in sources if source.id in ids]
    return sources


def repo_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else str(path)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- Fetch -------------------------------------------------------------------


def download(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
        if response.headers.get("Content-Encoding") == "gzip":  # servers that insist on compression (eCFR)
            data = gzip.decompress(data)
        return data


def html_fragment(page: bytes, selector: str) -> bytes:
    """The element matching `selector`, as BeautifulSoup serialises it. Pages change with every
    request (session tokens, timestamps); the fragment holding the law text does not."""
    fragment = BeautifulSoup(page, "html.parser").select_one(selector)
    if fragment is None:
        raise SourceError(f"Selector {selector!r} matched nothing")
    return (str(fragment) + "\n").encode("utf-8")


def fetch(original: Original) -> bytes:
    if original.pause:
        time.sleep(original.pause)
    data = download(original.url, original.headers)
    if original.fetch == "zip-member":
        if not original.member:
            raise SourceError(f"{original.file}: zip-member needs `member`")
        archive = zipfile.ZipFile(io.BytesIO(data))
        if original.member not in archive.namelist():
            raise SourceError(
                f"{original.file.name}: the zip holds {', '.join(archive.namelist())}, not {original.member}"
            )
        return archive.read(original.member)
    if original.fetch == "html-fragment":
        if not original.selector:
            raise SourceError(f"{original.file}: html-fragment needs `selector`")
        return html_fragment(data, original.selector)
    return data


SAVED_FROM = re.compile(rb"saved from url=\(\d+\)(\S+?)\s*-->")


def saved_url(page: bytes) -> str | None:
    """The address a browser-saved page comes from: its `<!-- saved from url=(…) -->` marker."""
    match = SAVED_FROM.search(page[:8192])
    return match.group(1).decode("utf-8", "replace") if match else None


def same_saved_url(url: str, listed: str) -> bool:
    """A saved page's marker matches the original's URL: the browser percent-encodes it and may keep
    a scroll anchor (#Text), both of which are cosmetic here."""
    decode = urllib.parse.unquote
    return decode(url.split("#", 1)[0]) == decode(listed.split("#", 1)[0])


def fetch_saved(original: Original, page: bytes) -> bytes:
    """The original cut out of a page saved by hand in a browser, with the same cut fetch makes:
    the fragment for html-fragment, the file itself otherwise."""
    if original.fetch == "html-fragment":
        if not original.selector:
            raise SourceError(f"{original.file.name}: html-fragment needs `selector`")
        return html_fragment(page, original.selector)
    if original.fetch == "file":
        return page
    raise SourceError(f"{original.file.name}: --saved works for html-fragment and file originals")


def record_fetch(source: Source, original: Original, data: bytes, on: date) -> bool:
    """Write a freshly fetched original and update its sha256 and retrieved_on in source.yaml.
    Returns False when nothing changed."""
    digest = sha256(data)
    if digest == original.sha256 and original.file.exists():
        return False
    original.file.write_bytes(data)
    text = source.index.read_text()
    pattern = re.compile(rf"(retrieved_on: )\S+(\n\s+sha256: ){re.escape(original.sha256)}(?=\s)")
    updated, count = pattern.subn(rf"\g<1>{on.isoformat()}\g<2>{digest}", text)
    if count != 1:
        raise SourceError(f"{source.index}: write `retrieved_on` directly above `sha256` for {original.file.name}")
    source.index.write_text(updated)
    return True


# --- Verify ------------------------------------------------------------------


def strip_annotations(annotated: bytes) -> bytes:
    for pattern in STRIP_PATTERNS:
        annotated = pattern.sub(b"", annotated)
    return annotated


def _element_paths(data: bytes) -> tuple[dict, dict, dict]:
    """For every element in the XML: its path (tag + sibling index), its start-tag's end offset,
    and its lga:* attributes — all from one expat walk."""
    paths: dict[tuple, int] = {}
    annotated: dict[tuple, dict] = {}
    texts: dict[tuple, list] = {}
    stack: list[tuple[str, int]] = []
    counts: dict[tuple, int] = {}
    parser = xml.parsers.expat.ParserCreate()

    def start(tag, attrs):
        parent = tuple(stack)
        counts[parent + (tag,)] = counts.get(parent + (tag,), 0) + 1
        stack.append((tag, counts[parent + (tag,)]))
        lga = {k: v for k, v in attrs.items() if k.startswith("lga:")}
        if lga:
            annotated[tuple(stack)] = lga
        i = parser.CurrentByteIndex
        while True:
            j = data.index(b">", i)
            inside = data[i:j]
            if inside.count(b'"') % 2 == 0 and inside.count(b"'") % 2 == 0:
                break
            i = j + 1
        paths[tuple(stack)] = j

    def end(tag):
        stack.pop()

    def chars(s):
        # An element's text is its own and its descendants' — collect against every prefix path.
        for i in range(1, len(stack) + 1):
            texts.setdefault(tuple(stack[:i]), []).append(s)

    parser.StartElementHandler, parser.EndElementHandler, parser.CharacterDataHandler = start, end, chars
    parser.Parse(data, True)
    return paths, annotated, texts


def reannotate(old_annotated: bytes, new_original: bytes) -> tuple[bytes, list[str]]:
    """Carry every lga: attribute of the old annotated XML onto the new original, byte-exact.

    Each annotated element is addressed by its path (tag + sibling index); elements whose text
    changed since annotation are reported and left unannotated rather than quoting wrong text.
    """
    _, old_anns, old_texts = _element_paths(old_annotated)
    new_ends, _, new_texts = _element_paths(new_original)
    problems, inserts = [], []
    root = next(iter(new_ends), None)
    if old_anns and root is not None and root not in old_anns:
        old_anns = {root: {}, **old_anns}  # the root declares xmlns:lga even when it has no lga: attributes
    for path, attrs in old_anns.items():
        if path not in new_ends:
            problems.append(f"<{path[-1][0]}>: element no longer exists")
            continue
        old_t = re.sub(r"\s+", " ", "".join(old_texts.get(path, []))).strip()
        new_t = re.sub(r"\s+", " ", "".join(new_texts.get(path, []))).strip()
        if old_t != new_t and len(path) > 1:
            problems.append(f"<{path[-1][0]}>: text changed, annotation left out")
            continue
        attrs = dict(attrs)
        if len(path) == 1:  # the root also carries xmlns:lga
            attrs = {"xmlns:lga": ANNOTATION_NS, **attrs}
        before = 1 if new_original[new_ends[path] - 1 : new_ends[path]] == b"/" else 0
        # Double-quoted and escaped, as strip_annotations() expects: expat handed the values back unescaped.
        text = "".join(f' {k}="{xml.sax.saxutils.escape(v, {chr(34): "&quot;"})}"' for k, v in attrs.items())
        inserts.append((new_ends[path] - before, text))
    out = new_original
    for offset, text in sorted(inserts, reverse=True):
        out = out[:offset] + text.encode() + out[offset:]
    return out, problems


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def annotation(element: ET.Element, name: str) -> str | None:
    return element.get(f"{{{ANNOTATION_NS}}}{name}")


def annotation_names(element: ET.Element) -> set[str]:
    prefix = f"{{{ANNOTATION_NS}}}"
    return {key.removeprefix(prefix) for key in element.attrib if key.startswith(prefix)}


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def text_of(media_type: str, data: bytes, text_ignore: list[str]) -> str:
    """An original's text as it is compared word for word: for HTML, the words with the elements
    text_ignore names left out."""
    if media_type == "application/pdf":
        return pdf_text(data)
    soup = BeautifulSoup(data, "html.parser")
    for selector in text_ignore:
        for element in soup.select(selector):
            element.decompose()
    return collapse(soup.get_text(" "))


def original_text(original: Original) -> str:
    return text_of(original.media_type, original.file.read_bytes(), original.text_ignore)


def same_text(original: Original, data: bytes) -> bool:
    """The fetched page has the same words as the committed original: markup-only drift (timestamps,
    browser-saved pages, rewritten asset links) does not count as a changed text."""
    if original.media_type != "text/html" or not original.file.exists():
        return False
    return comparable(original_text(original), original.media_type) == comparable(
        text_of(original.media_type, data, original.text_ignore), original.media_type
    )


@functools.cache
def pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return collapse(" ".join(page.extract_text() or "" for page in reader.pages))


def comparable(text: str, media_type: str) -> str:
    """Text as compared word for word (dashes as one character, footnote marks set directly after a
    word left out). Text taken from a PDF has its line breaks, hyphenation,
    ligatures and spacing decided by the layout, so for PDFs the comparison is on letters only:
    Unicode compatibility forms (NFKC: "ﬁ" is "fi"), without whitespace and hyphens. The words and
    their order must still match exactly."""
    # Typesetting that differs between an Official Journal page and its XML: dash variants, and
    # footnote marks set directly after a word ("assessment(29).").
    text = re.sub(r"[\u2012\u2013\u2014\u2015\u2212]", "-", text)
    text = re.sub(r"(?<=[^\W\d_])\(\d{1,3}\)", "", text)
    if media_type != "application/pdf":
        return collapse(text)
    return re.sub(r"[\s\-\u00ad\u2010\u2011]+", "", unicodedata.normalize("NFKC", text))


def verify(source: Source) -> list[str]:
    errors = []
    for original in source.originals:
        if not original.file.exists():
            errors.append(f"{repo_path(original.file)}: missing; run `legalgraph sources fetch {source.id}`")
        elif sha256(original.file.read_bytes()) != original.sha256:
            errors.append(f"{repo_path(original.file)}: SHA-256 differs from source.yaml (originals are never edited)")
    if errors:
        return errors
    annotated = source.annotated.read_bytes()
    where = repo_path(source.annotated)
    try:
        root = ET.fromstring(annotated)
    except ET.ParseError as error:
        return [f"{where}: {error}"]

    if source.kind == "official-xml":
        if len(source.texts) != 1:
            errors.append(f"{repo_path(source.index)}: official-xml has exactly one original with role text")
        elif strip_annotations(annotated) != source.texts[0].file.read_bytes():
            errors.append(f"{where}: without its lga: attributes it is not byte-identical to the original")
        if any(original.annotated for original in source.parallels):
            errors.append(f"{repo_path(source.index)}: `annotated` on a parallel is for authored translations")
        errors += verify_parallels(source, root)
        errors += verify_consolidation(source, root) if source.authentic else verify_corrigenda(source, root)
    else:
        schema = etree.XMLSchema(etree.parse(LAW_SCHEMA))
        if not schema.validate(etree.fromstring(annotated)):
            errors += [f"{where}:{entry.line}: {entry.message}" for entry in schema.error_log]
        texts: dict[str, str] = {}
        for section in root.iter(f"{{{LAW_NS}}}section"):
            original = source.original(section.get("source", ""))
            if original.media_type not in ("text/html", "application/pdf"):
                continue  # other formats: the wording is compared by a reviewer
            haystack = texts.setdefault(original.file.name, comparable(original_text(original), original.media_type))
            for paragraph in section.iter(f"{{{LAW_NS}}}paragraph"):
                # A PDF's page headers and footers can fall between two lines, so there each line
                # (paragraph lead-in, numbered item) is compared on its own; elsewhere the paragraph.
                marked = "\n".join(line.text for line in render_lines(paragraph, marks=True))
                if original.media_type == "application/pdf":
                    marked = marked.replace("\n", NOTE_MARK)
                if any(comparable(part, original.media_type) not in haystack for part in marked.split(NOTE_MARK)):
                    errors.append(
                        f"{where}: {section.get('num')} {paragraph.get('num', '')}: text does not occur word for "
                        f"word in {original.file.name}"
                    )
        errors += verify_authored_parallels(source, root, schema)

    for element in root.iter():
        names = annotation_names(element)
        allowed = (
            ROOT_ATTRIBUTES if element is root else PROVISION_ATTRIBUTES if "provision" in names else ITEM_ATTRIBUTES
        )
        if unknown := names - allowed:
            errors.append(f"{where}: <{local(element.tag)}> has unknown annotation(s) {sorted(unknown)}")
    return errors


def element_at(root: ET.Element, path: str) -> ET.Element | None:
    """The element at an XPath made by xpath() (/ROOT/CHILD[n]/…), or None."""
    steps = path.strip("/").split("/")
    if not steps or local(root.tag) != steps[0]:
        return None
    element = root
    for step in steps[1:]:
        match = re.fullmatch(r"([^\[]+)\[(\d+)\]", step)
        if not match:
            return None
        same = [child for child in element if local(child.tag) == match.group(1)]
        index = int(match.group(2)) - 1
        if index >= len(same):
            return None
        element = same[index]
    return element


def provision_elements(root: ET.Element) -> list[ET.Element]:
    return [element for element in root.iter() if element is not root and annotation(element, "provision")]


def verify_parallels(source: Source, root: ET.Element) -> list[str]:
    """Each provision must be at the same place in every other language version, with the same
    identifiers and the same number of lines, so the versions can be read side by side."""
    errors = []
    parents = {child: parent for parent in root.iter() for child in parent}
    for parallel in source.parallels:
        other = ET.fromstring(parallel.file.read_bytes())
        name = parallel.file.name
        for element in provision_elements(root):
            path = xpath(element, parents)
            match = element_at(other, path)
            label = annotation(element, "provision")
            if match is None or local(match.tag) != local(element.tag):
                errors.append(f"{name}: no <{local(element.tag)}> at {path} for {label}")
            elif match.get("IDENTIFIER") != element.get("IDENTIFIER") or match.get("eId") != element.get("eId"):
                errors.append(
                    f"{name}: {path} has IDENTIFIER {match.get('IDENTIFIER')!r}, not {element.get('IDENTIFIER')!r}"
                )
            elif (theirs := len(render_lines(match))) != (ours := len(render_lines(element))):
                errors.append(f"{name}: {label} has {theirs} lines, the annotated text {ours}")
    return errors


# An authored parallel (a translation written in schemas/law.xsd) annotates only where a provision is
# and where it is published: lga:provision and lga:url; the root carries the usual act attributes.
PARALLEL_PROVISION_ATTRIBUTES = {"provision", "url"}


def verify_authored_parallels(source: Source, root: ET.Element, schema: etree.XMLSchema) -> list[str]:
    """The parallel language versions of an authored source are translations the maintainers write
    in schemas/law.xsd (e.g. the Rada's official English of a Ukrainian act): the parallel's
    `annotated` names that file. Its words are checked against its own original, every provision it
    carries must exist in the annotated text with the same number of lines (matched by
    lga:provision, not position), and lga:provision and lga:url are the only annotations allowed.
    A provision the translation does not carry simply gets no official English."""
    errors = []
    provisions = {annotation(element, "provision"): element for element in provision_elements(root)}
    texts: dict[str, str] = {}
    for parallel in source.parallels:
        if parallel.annotated is None:
            errors.append(
                f"{repo_path(source.index)}: {parallel.file.name} is a parallel of an authored-xml "
                "source and needs `annotated`, its translation in schemas/law.xsd"
            )
            continue
        where = repo_path(parallel.annotated)
        if not parallel.annotated.exists():
            errors.append(f"{where}: missing")
            continue
        try:
            p_root = ET.fromstring(parallel.annotated.read_bytes())
        except ET.ParseError as error:
            errors.append(f"{where}: {error}")
            continue
        if not schema.validate(etree.fromstring(parallel.annotated.read_bytes())):
            errors += [f"{where}:{entry.line}: {entry.message}" for entry in schema.error_log]
        for element in p_root.iter():
            names = annotation_names(element)
            allowed = ROOT_ATTRIBUTES if element is p_root else PARALLEL_PROVISION_ATTRIBUTES
            if unknown := names - allowed:
                errors.append(f"{where}: <{local(element.tag)}> has unknown annotation(s) {sorted(unknown)}")
        for section in p_root.iter(f"{{{LAW_NS}}}section"):
            try:
                original = source.original(section.get("source", ""))
            except SourceError:
                errors.append(f"{where}: section {section.get('num')}: unknown source {section.get('source')!r}")
                continue
            if original is not parallel:
                errors.append(
                    f"{where}: section {section.get('num')}: its words must come from {parallel.file.name}, "
                    f"not {original.file.name}"
                )
                continue
            if original.media_type not in ("text/html", "application/pdf"):
                continue
            haystack = texts.setdefault(original.file.name, comparable(original_text(original), original.media_type))
            for paragraph in section.iter(f"{{{LAW_NS}}}paragraph"):
                marked = "\n".join(line.text for line in render_lines(paragraph, marks=True))
                if original.media_type == "application/pdf":
                    marked = marked.replace("\n", NOTE_MARK)
                if any(comparable(part, original.media_type) not in haystack for part in marked.split(NOTE_MARK)):
                    errors.append(
                        f"{where}: {section.get('num')} {paragraph.get('num', '')}: text does not occur word for "
                        f"word in {original.file.name}"
                    )
        for element in provision_elements(p_root):
            label = annotation(element, "provision")
            main = provisions.get(label)
            if main is None:
                errors.append(f"{where}: {label}: no such provision in {repo_path(source.annotated)}")
            elif (theirs := len(render_lines(element))) != (ours := len(render_lines(main))):
                errors.append(f"{where}: {label} has {theirs} lines, the annotated text {ours}")
        if parallel.as_of:
            errors += verify_translation_date(source, root, parallel, p_root)
    return errors


AMENDMENT_NOTE = re.compile(r"\{[^{}]*\}")
# zakon.rada.gov.ua dates its editorial notes "від DD.MM.YYYY" (№ of the amending act follows №).
AMENDED_ON = re.compile(r"від (\d{1,2})\.(\d{1,2})\.(\d{4})")


def original_full_text(original: Original) -> str:
    """The original's text as the portal serves it, including the editorial notes text_ignore
    removes for the word check."""
    return collapse(BeautifulSoup(original.file.read_bytes(), "html.parser").get_text(" "))


def verify_translation_date(source: Source, root: ET.Element, parallel: Original, p_root: ET.Element) -> list[str]:
    """An official translation older than the provision it translates must not stand as its
    English. The original marks each amendment with an editorial note (`{… Законом № … від
    DD.MM.YYYY}`) — inside text_ignore's elements, so it is not part of the checked words. A note
    dated after the parallel's `as_of` inside, or directly after, a translated provision fails."""
    errors = []
    parents = {child: parent for parent in root.iter() for child in parent}
    haystacks: dict[str, str] = {}
    for element in provision_elements(p_root):
        label = annotation(element, "provision")
        main = next((e for e in provision_elements(root) if annotation(e, "provision") == label), None)
        if main is None:
            continue  # reported by verify_authored_parallels
        name = section_source(main, parents) if len(source.texts) > 1 else source.texts[0].file.name
        original = source.original(name)
        if original.media_type != "text/html":
            continue  # the amendment-note convention is the portal's HTML one
        haystack = haystacks.setdefault(name, comparable(original_full_text(original), original.media_type))
        lines = [comparable(line.text, original.media_type) for line in render_lines(main)]
        if not all(lines):
            continue
        start = haystack.find(lines[0])
        if start < 0:
            continue  # the word check reports text missing from the original
        end = haystack.find(lines[-1], start) + len(lines[-1])
        # Notes the portal sets between the provision's lines, or directly after its last one.
        region = haystack[start:end]
        rest = haystack[end:]
        while match := re.match(r"\s*\{[^{}]*\}", rest):
            region += match.group(0)
            rest = rest[match.end() :]
        for note in AMENDMENT_NOTE.findall(region):
            amended = [date(int(y), int(m), int(d)) for d, m, y in AMENDED_ON.findall(note)]
            if amended and max(amended) > parallel.as_of:
                errors.append(
                    f"{repo_path(parallel.annotated)}: {label}: amended on {max(amended).isoformat()} "
                    f"by a note in {name}, after the translation of {parallel.as_of.isoformat()}"
                )
                break
    return errors


CHANGED_PLACE = re.compile(r"(?:Art\. (\d+[a-z]?)(?:\((\d+)\))?|Recital (\d+)|Annex ([IVX]+)(?:\((\w+)\))?)")
# ("art", "11a", paragraph or point), ("rec", "30", None) or ("annex", "I", point such as "23b")
Place = tuple[str, str, str | None]


def article_number(identifier: str) -> str:
    """Formex IDENTIFIER "011A" → "11a"."""
    return identifier.lstrip("0").lower()


def point_label(element: ET.Element) -> str:
    """ "(23b)" or "23b." → "23b"."""
    number = element.find("NP/NO.P")
    return re.sub(r"[^0-9A-Za-z]", "", "".join(number.itertext())).lower() if number is not None else ""


def formex_place(element: ET.Element, parents: dict[ET.Element, ET.Element]) -> Place | None:
    """Where an element of a Formex text is, for matching the places corrigenda and amending acts
    change: an article and its paragraph or point, a recital, or an annex and its point."""
    sub: str | None = None
    node: ET.Element | None = element
    while node is not None:
        name = local(node.tag)
        if name == "CONSID":
            number = re.sub(r"\D", "", point_label(node))
            return ("rec", number.lstrip("0"), None) if number else None
        if name == "PARAG" and node.get("IDENTIFIER"):
            sub = str(int(re.sub(r"\D", "", node.get("IDENTIFIER", "").split(".")[-1]) or 0))
        elif name == "ITEM" and sub is None and (label := point_label(node)):
            sub = label
        elif name == "ARTICLE" and node.get("IDENTIFIER"):
            return "art", article_number(node.get("IDENTIFIER", "")), sub
        elif name in ("ANNEX", "CONS.ANNEX"):  # an annex, in an Official Journal or a consolidated text
            title = node.find("TITLE/TI")
            numeral = re.search(r"\b([IVX]+)\b", collapse("".join(title.itertext()))) if title is not None else None
            return "annex", numeral.group(1) if numeral else "I", sub
        node = parents.get(node)
    return None


def changed_places(original: Original) -> list[Place]:
    places: list[Place] = []
    for place in original.corrects:
        if place == "Whole text":  # a correction applied throughout ("Gesamter Text")
            places.append(("all", "", None))
        elif match := CHANGED_PLACE.match(place):
            if match.group(3):
                places.append(("rec", match.group(3).lstrip("0"), None))
            elif match.group(4):
                places.append(("annex", match.group(4), match.group(5).lower() if match.group(5) else None))
            else:
                places.append(("art", match.group(1).lower(), match.group(2)))
    return places


def covers(change: Place, place: Place) -> bool:
    if change[0] == "all":
        return True
    return change[:2] == place[:2] and (change[2] is None or place[2] in (None, change[2]))


def verify_corrigenda(source: Source, root: ET.Element) -> list[str]:
    """When the annotated text is the Official Journal text itself, a corrigendum that corrects an
    annotated provision must be applied first. `corrects` in source.yaml lists the places each
    corrigendum changes (Art. 4(18), Recital 71, …)."""
    errors = []
    parents = {child: parent for parent in root.iter() for child in parent}
    for corrigendum in source.corrigenda:
        for place, change in zip(corrigendum.corrects, changed_places(corrigendum), strict=False):
            for element in provision_elements(root):
                found = formex_place(element, parents)
                if found and covers(change, found):
                    errors.append(
                        f"{corrigendum.file.name} corrects {place}, which {annotation(element, 'provision')} quotes"
                    )
    return errors


def formex_key(element: ET.Element, parents: dict[ET.Element, ET.Element]) -> list[tuple[str, str]]:
    """How to find the same element in another Formex text of the act: its ARTICLE and PARAG
    identifiers, ITEM numbers and recital number, outermost first."""
    key = []
    node: ET.Element | None = element
    while node is not None:
        name = local(node.tag)
        if name in ("ARTICLE", "PARAG") and node.get("IDENTIFIER"):
            key.append((name, node.get("IDENTIFIER", "")))
        elif name in ("ITEM", "CONSID") and node.find("NP/NO.P") is not None:
            key.append((name, collapse("".join(node.find("NP/NO.P").itertext()))))
        node = parents.get(node)
    return list(reversed(key))


def find_by_key(root: ET.Element, key: list[tuple[str, str]]) -> ET.Element | None:
    scope: ET.Element | None = root
    for name, value in key:
        if scope is None:
            return None
        if name in ("ARTICLE", "PARAG"):
            scope = next((e for e in scope.iter(name) if e.get("IDENTIFIER") == value), None)
        else:
            scope = next(
                (
                    e
                    for e in scope.iter(name)
                    if e.find("NP/NO.P") is not None and collapse("".join(e.find("NP/NO.P").itertext())) == value
                ),
                None,
            )
    return scope


def trim(line: str) -> str:
    """A line without its final punctuation and a trailing "and" / "or"."""
    return re.sub(r"(?:[.;,:]|;? (?:and|or|und|oder))$", "", line.strip()).rstrip()


def plain_quotes(text: str) -> str:
    return re.sub("[‘’‚‛“”„‟«»‹›\"']", '"', text)


def authentic_form(text: str, media_type: str) -> str:
    """Text as compared with an authentic PDF or HTML: word for word (comparable), with quote marks
    and apostrophes alike, since the Official Journal and its XML typeset them differently (subject’s,
    subject's), as the amendment check does."""
    return plain_quotes(comparable(text, media_type))


def verify_consolidation(source: Source, root: ET.Element) -> list[str]:
    """A consolidated text (the act with its corrigenda and amendments worked in, which the
    Publications Office publishes as a documentation tool) is checked against the authentic texts:
    every line of a quoted provision (a subparagraph or point) must read exactly as in the Official
    Journal publication of the act (role: authentic), unless a corrigendum or amending act of the same
    language lists its place; a line an amending act changed must occur word for word in that act."""
    errors = []
    parents = {child: parent for parent in root.iter() for child in parent}
    consolidated = [(source.texts[0], root)] + [(o, ET.fromstring(o.file.read_bytes())) for o in source.parallels]
    for original, tree in consolidated:
        tree_parents = parents if tree is root else {child: parent for parent in tree.iter() for child in parent}
        language = source.language_of(original)
        authentic = [o for o in source.authentic if source.language_of(o) == language]
        if not authentic:
            errors.append(f"{repo_path(source.index)}: no authentic text in {language} for {original.file.name}")
            continue
        # The authentic text is Formex where the Official Journal has it (from 2004), else its HTML or PDF.
        media = authentic[0].media_type
        textual = media in ("application/pdf", "text/html")
        reference = None if textual else ET.fromstring(authentic[0].file.read_bytes())
        haystack = authentic_form(original_text(authentic[0]), media) if textual else ""
        changes = [o for o in source.corrigenda + source.amendments if source.language_of(o) == language]
        for element in provision_elements(root):
            label = annotation(element, "provision")
            current = element if tree is root else element_at(tree, xpath(element, parents))
            if current is None:
                continue  # reported by verify_parallels
            # A line whose only difference is its final punctuation (a list's last point that became a
            # middle one when an amendment added a point after it) counts as unchanged.
            if textual:
                unchanged = {
                    trim(line.text)
                    for line in render_lines(current)
                    if authentic_form(trim(line.text), media) in haystack
                }
            else:
                before = find_by_key(reference, formex_key(current, tree_parents)) if reference is not None else None
                unchanged = {trim(line.text) for line in render_lines(before)} if before is not None else set()
            changed = [line.text for line in render_lines(current) if trim(line.text) not in unchanged]
            if not changed:
                continue
            place = formex_place(element, parents)
            explained = [o for o in changes if place and any(covers(c, place) for c in changed_places(o))]
            if not explained:
                errors.append(
                    f"{original.file.name}: {label} differs from the authentic text {authentic[0].file.name} "
                    "and no corrigendum or amending act in source.yaml lists its place"
                )
                continue
            amendments = [o for o in explained if o.role == "amendment"]
            if amendments and not any(o.role == "corrigendum" for o in explained):
                # Quoted in an amending act, the text's own quotation marks become inner ones
                # (‘…’ turns into “…”), so quotation marks are compared as one character, and
                # the final punctuation of a list point differs the same way as against the
                # authentic text (the amending quote may end where the list's ';' belongs to
                # the instrument's own wording).
                bodies = [plain_quotes(collapse(render(ET.fromstring(o.file.read_bytes())))) for o in amendments]
                for line in changed:
                    if not any(plain_quotes(collapse(trim(line))) in body for body in bodies):
                        names = ", ".join(o.file.name for o in amendments)
                        errors.append(
                            f"{original.file.name}: {label}: “{line[:60]}…” does not occur word for word in {names}"
                        )
    return errors


# --- Extract -----------------------------------------------------------------


def xpath(element: ET.Element, parents: dict[ET.Element, ET.Element]) -> str:
    steps = []
    while element in parents:
        parent = parents[element]
        same = [child for child in parent if child.tag == element.tag]
        steps.append(f"{local(element.tag)}[{same.index(element) + 1}]")
        element = parent
    steps.append(local(element.tag))
    return "/" + "/".join(reversed(steps))


SKIPPED = {"FnR", "NOTE", "CommentaryRef", "FootnoteRef", "authorialNote"}
BLOCKS = {"ITEM", "ALINEA", "P2", "P3", "P4", "P5"}
NUMBERS = {"NO.PARAG", "NO.P", "Pnumber", "num"}  # num: Akoma Ntoso (Fedlex)


@dataclass
class Line:
    text: str
    requires: list[str] = field(default_factory=list)
    defines: list[str] = field(default_factory=list)


LINE_ANNOTATIONS = ("requires", "defines")


NOTE_MARK = "\u2063"  # where a footnote mark of an authored text sits, for the word check only


def render_lines(element: ET.Element, marks: bool = False) -> list[Line]:
    """The text of an element as a reader sees it, line by line, by fixed rules for every XML dialect
    read here, with the item annotations (lga:requires, lga:defines) that apply to each line.

    Whitespace inside text collapses to one space. A list item starts a new line with its number
    (gesetze-im-internet.de: <DT>number</DT><DD>text</DD>; Formex: <ITEM><NP><NO.P>number</NO.P>
    <TXT>text</TXT></NP></ITEM>; authored XML: <item num="…">), and a list ends its line. A
    paragraph's number comes first (authored: num attribute; Formex: <NO.PARAG>; legislation.gov.uk:
    <Pnumber>, shown as "(1)", or "1." for a top-level <P1>). A block starts a new line unless the
    line holds only a number: in Formex each subparagraph (<ALINEA>, or a <P> inside one); on
    legislation.gov.uk each <P2>…<P5> and each <Text> of a paragraph; in the eCFR each <P>. Formex
    quotation marks (<QUOT.START>, <QUOT.END>) are the characters their CODE names. <BR/> is a line
    break; footnotes and commentary marks (<FnR>, <NOTE>, <CommentaryRef>, <FootnoteRef>) are
    skipped. Empty lines are dropped.
    """
    lines: list[dict[str, list[str]]] = []

    def newline() -> None:
        lines.append({"chunks": [], "requires": [], "defines": [], "prefix": []})

    def text(value: str | None) -> None:
        if value:
            lines[-1]["chunks"].append(re.sub(r"\s+", " ", value))

    def number(value: str) -> None:
        text(f"{value} ")
        lines[-1]["prefix"].append(value)

    def soft_break() -> None:
        """New line, unless the current one is empty or holds only a number."""
        current = collapse("".join(lines[-1]["chunks"]))
        if current and current != collapse(" ".join(lines[-1]["prefix"])):
            newline()

    def walk(node: ET.Element, parent: str) -> None:
        name = local(node.tag)
        if name in SKIPPED:
            return
        if name in ("note", "page"):  # footnote mark or page break in authored XML: not part of the text
            if marks:
                text(NOTE_MARK)
            return
        if name in ("QUOT.START", "QUOT.END"):
            text(chr(int(node.get("CODE", "22"), 16)))
            return
        if name in ("DT", "BR", "br"):
            newline()
        elif name == "DD":
            text(" ")
        elif name == "item" and node.get("num") is not None:  # authored XML; Akoma Ntoso items have <num>
            newline()
            text(f"{node.get('num', '')} ")
        elif name == "item":
            soft_break()
        elif name == "paragraph" and node.get("num"):
            text(f"{node.get('num')} ")
        elif (
            name in BLOCKS
            or (name == "P" and parent in ("ALINEA", "DIV8", "SECTION"))
            or (name == "p" and parent == "content")
            or (name == "Text" and parent.endswith("para"))
        ):
            soft_break()
        for key in LINE_ANNOTATIONS:
            lines[-1][key].extend((annotation(node, key) or "").split())
        if name in NUMBERS:
            value = collapse("".join(node.itertext()))
            number(value if name != "Pnumber" else f"{value}." if parent == "P1" else f"({value})")
            return
        text(node.text)
        previous = None
        for child in node:
            if previous == "LA" and local(child.tag) == "LA":
                text(" ")  # two text blocks of one item (gesetze-im-internet.de): a heading and its text
            walk(child, name)
            if local(child.tag) in ("DL", "list", "LIST"):
                newline()
            text(child.tail)
            previous = local(child.tag)

    newline()
    walk(element, "")
    result: list[Line] = []
    carried: dict[str, list[str]] = {key: [] for key in LINE_ANNOTATIONS}
    for entry in lines:
        line = re.sub(r" +", " ", "".join(entry["chunks"])).strip()
        if line:
            result.append(Line(line, carried["requires"] + entry["requires"], carried["defines"] + entry["defines"]))
            carried = {key: [] for key in LINE_ANNOTATIONS}
        else:
            for key in LINE_ANNOTATIONS:
                carried[key] += entry[key]  # an annotation on an element that starts with an empty line
    return result


def render(element: ET.Element) -> str:
    """The text of an element as one string, one line per paragraph or list item (see render_lines)."""
    return "\n".join(line.text for line in render_lines(element))


def required(element: ET.Element, name: str, where: str) -> str:
    value = annotation(element, name)
    if not value:
        raise SourceError(f"{where}: <{local(element.tag)}> is missing lga:{name}")
    return value


def act_metadata(root: ET.Element) -> tuple[str | None, str | None, str | None, list[str]]:
    """Title, short name, date and status notes from the document's own metadata."""

    def first(element: ET.Element | None) -> str | None:
        return render(element) if element is not None else None

    def iso_date(element: ET.Element | None) -> str | None:
        iso = element.get("ISO", "") if element is not None else ""
        return f"{iso[:4]}-{iso[4:6]}-{iso[6:]}" if len(iso) == 8 else None

    name = local(root.tag)
    if name in ("ACT", "CONS.ACT"):  # Formex: title from the act itself, date of signature
        title = root.find("TITLE/TI") if name == "ACT" else root.find("CONS.DOC/FAM.COMP/BIB.DATA/TITLE/TI")
        lines = [render(paragraph) for paragraph in title.iterfind("P")] if title is not None else []
        if len(lines) > 1 and lines[-1].startswith("(") and lines[-1].endswith(")"):
            lines = lines[:-1]  # a last line wholly in brackets is the "(Text with EEA relevance)" note
        signed = (
            root.find("BIB.INSTANCE/DATE") if name == "ACT" else title.find(".//DATE") if title is not None else None
        )
        return " ".join(lines) or None, None, iso_date(signed), []
    if (
        name == "JUDGMENT"
    ):  # Formex judgment: "Judgment of the Court (Grand Chamber) of 1 October 2019, Planet49, C-673/17"
        title = root.find("TITLE/TI")
        lines = [render(paragraph) for paragraph in title.iterfind("P")] if title is not None else []
        case = root.find("BIB.JUDGMENT/REF.CASE/NO.CASE")
        names = root.findall("CURR.TITLE/PAGE.HEADER/P")
        parts = [" of ".join(lines), render(names[-1]) if names else "", render(case) if case is not None else ""]
        return (
            ", ".join(part for part in parts if part) or None,
            None,
            iso_date(title.find(".//DATE") if title is not None else None),
            [],
        )
    if name == "akomaNtoso":  # Akoma Ntoso (Fedlex): the work's name in the document's language
        akn = f"{{{AKN_NS}}}"
        work = root.find(f".//{akn}FRBRWork")
        language = root.find(f".//{akn}FRBRExpression/{akn}FRBRlanguage")
        code = {"deu": "de", "fra": "fr", "ita": "it", "eng": "en", "roh": "rm"}.get(
            language.get("language", "") if language is not None else "", "de"
        )
        names = [n for n in work.iterfind(f"{akn}FRBRname")] if work is not None else []
        own = next((n for n in names if n.get("{http://www.w3.org/XML/1998/namespace}lang") == code), None)
        dated = next(
            (
                d
                for d in (work.iterfind(f"{akn}FRBRdate") if work is not None else [])
                if d.get("name") == "jolux:dateDocument"
            ),
            None,
        )
        return (
            own.get("value") if own is not None else None,
            own.get("shortForm") if own is not None else None,
            dated.get("date") if dated is not None else None,
            [],
        )
    if name == "Legislation":  # legislation.gov.uk: title from the metadata, date made
        dc = "{http://purl.org/dc/elements/1.1/}"
        ukm = "{http://www.legislation.gov.uk/namespaces/metadata}"
        title = root.find(f"{ukm}Metadata/{dc}title")
        made = root.find(f".//{ukm}Made")
        return (
            collapse(title.text or "") if title is not None else None,
            None,
            made.get("Date") if made is not None else None,
            [],
        )
    if local(root.tag) == "law":
        meta = root.find(f"{{{LAW_NS}}}meta")
        if meta is None:
            return None, None, None, []
        return (
            first(meta.find(f"{{{LAW_NS}}}title")),
            first(meta.find(f"{{{LAW_NS}}}short")),
            first(meta.find(f"{{{LAW_NS}}}date")),
            [],
        )
    metadata = root.find("norm/metadaten")
    if metadata is None:
        return None, None, None, []
    short = metadata.find("amtabk")
    if short is None:
        short = metadata.find("jurabk")
    notes = [render(note) for note in metadata.iterfind("standangabe/standkommentar")]
    return first(metadata.find("langue")), first(short), first(metadata.find("ausfertigung-datum")), notes


REFERENCE = re.compile(
    r"\b(?:Articles? (?P<articles>\d+(?:\(\d+\))?(?:(?:, | and | or | to )\d+(?:\(\d+\))?)*)"
    r"|paragraphs? (?P<paragraphs>\d+(?:(?:, | and | or | to )\d+)*))"
    r"(?! of (?:the |this )?(?:Directive|Regulation|Decision|Charter|Treaty|TFEU|Council))"
)


def internal_references(text: str, act: str, own_article: str | None) -> list[str]:
    """Identifiers of the provisions an EU act's text points to within the same act: Article N(M) is
    <act>-artN-M, Article N any provision of article N, paragraph M of the provision's own article.
    References to other acts ("Article 8 of the Charter") are left out."""
    found: list[str] = []
    for match in REFERENCE.finditer(text):
        if match.group("articles"):
            parts = re.split(r", | and | or | to ", match.group("articles"))
            ranged = " to " in match.group("articles")
            for part in parts:
                number = re.fullmatch(r"(\d+)(?:\((\d+)\))?", part)
                if number:
                    found.append(f"{act}-art{number.group(1)}" + (f"-{number.group(2)}" if number.group(2) else ""))
            if ranged and len(parts) == 2 and all(part.isdigit() for part in parts):
                found += [f"{act}-art{n}" for n in range(int(parts[0]) + 1, int(parts[1]))]
        elif own_article:
            for part in re.split(r", | and | or | to ", match.group("paragraphs")):
                found.append(f"{act}-art{own_article}-{part}")
    # "Article N" without a paragraph: every provision of the article; resolved by the caller's prefix match.
    return [target for ref in found for target in expand_article(ref)]


def expand_article(reference: str) -> list[str]:
    return (
        [reference]
        if re.search(r"-art\d+-\d+$", reference)
        else [reference, *(f"{reference}-{n}" for n in range(1, 30))]
    )


def decision_identifier(root: ET.Element) -> str | None:
    """The European Case Law Identifier of a Formex judgment."""
    ecli = root.find("BIB.JUDGMENT/NO.ECLI")
    return ecli.get("ECLI") if ecli is not None else None


def inside_provision(element: ET.Element, parents: dict[ET.Element, ET.Element]) -> bool:
    """The element is a provision or lies inside one."""
    if annotation(element, "provision"):
        return True
    while element in parents:
        element = parents[element]
        if annotation(element, "provision"):
            return True
    return False


def section_source(element: ET.Element, parents: dict[ET.Element, ET.Element]) -> str:
    while element in parents:
        element = parents[element]
        if local(element.tag) == "section":
            return element.get("source", "")
    raise SourceError("Provision outside a <section>")


def extract(source: Source) -> str:
    root = ET.fromstring(source.annotated.read_bytes())
    parents = {child: parent for parent in root.iter() for child in parent}
    graph = Graph()
    where = repo_path(source.annotated)
    lang = source.language
    act = LG[required(root, "act", where)]
    act_name = act.removeprefix(str(LG))
    # A parallel's text is the file itself for official XML, or its own authored XML for a
    # translation written in schemas/law.xsd (`annotated` on the original).
    parallel_roots = {
        original.file.name: ET.fromstring((original.annotated or original.file).read_bytes())
        for original in source.parallels
    }
    parallel_parents = {
        name: {child: parent for parent in tree.iter() for child in parent} for name, tree in parallel_roots.items()
    }
    title, short, issued, notes = act_metadata(root)

    documents: dict[str, URIRef] = {}
    for number, original in enumerate(source.texts, 1):
        base = source.document or f"{act_name}-source"
        documents[original.file.name] = LG[base if len(source.texts) == 1 else f"{base}-{number}"]
    for original in source.parallels:
        documents[original.file.name] = LG[f"{source.document or f'{act_name}-source'}-{source.language_of(original)}"]
    for original in source.texts + source.parallels:
        document = documents[original.file.name]
        graph.add((document, RDF.type, LGO.SourceDocument))
        graph.add((document, DCTERMS.language, Literal(source.language_of(original), datatype=XSD.language)))
        graph.add((document, LGO.repositoryPath, Literal(repo_path(original.file))))
        if original.role == "text":
            graph.add((document, LGO.annotatedFile, Literal(where)))
        graph.add((document, LGO.mediaType, Literal(original.media_type)))
        graph.add((document, LGO.sha256, Literal(original.sha256)))
        graph.add((document, LGO.sourceUrl, Literal(original.url, datatype=XSD.anyURI)))
        graph.add((document, LGO.retrievedOn, Literal(original.retrieved_on.isoformat(), datatype=XSD.date)))
        for note in notes:
            graph.add((document, LGO.legalStatus, Literal(note, lang=lang)))
        for note in original.notes:
            graph.add((document, LGO.legalStatus, Literal(note, lang="en")))
        if source.licence:
            graph.add((document, LGO.licence, LICENCES[source.licence]))
            graph.add((document, LGO.licenceBasis, Literal(source.licence_basis)))
        if builddate := root.get("builddate"):
            graph.add((document, LGO.portalBuildDate, Literal(builddate)))
        if original.role == "parallel":
            graph.add((document, LGO.languageVersionOf, documents[source.texts[0].file.name]))

    act_type = required(root, "act-type", where)
    graph.add((act, RDF.type, DOCUMENT_CLASSES.get(act_type, LGO.LegalAct)))
    if ecli := decision_identifier(root):
        graph.add((act, LGO.ecli, Literal(ecli)))
    graph.add((act, LGO.jurisdiction, LG[required(root, "jurisdiction", where)]))
    graph.add((act, LGO.actType, LGV[act_type]))
    graph.add((act, LGO.sourceUrl, Literal(required(root, "url", where), datatype=XSD.anyURI)))
    graph.add((act, LGO.reviewStatus, LGV.SourceChecked))
    for document in documents.values():
        graph.add((act, LGO.sourceDocument, document))
    for target in (annotation(root, "transposes") or "").split():
        graph.add((act, ELI.transposes, LG[target]))
    if title:
        graph.add((act, ELI.title, Literal(title, lang=lang)))
    if short:
        graph.add((act, LGO.shortName, Literal(short)))
    if issued:
        graph.add((act, ELI.date_document, Literal(issued, datatype=XSD.date)))

    for element in root.iter():
        if annotation(element, "requires") and not inside_provision(element, parents):
            raise SourceError(f"{where}: {xpath(element, parents)} has lga:requires outside a provision")

    for element in root.iter():
        if element is root or not annotation(element, "provision"):
            continue
        provision = LG[required(element, "provision", where)]
        if not any(annotation(node, role) for node in element.iter() for role in PROVISION_ROLES):
            raise SourceError(f"{where}: {provision} needs one of lga:{', lga:'.join(PROVISION_ROLES)}")
        file_name = section_source(element, parents) if len(source.texts) > 1 else source.texts[0].file.name
        document = documents[file_name]
        # A provision without a page of its own (EUR-Lex has none per article) links to the act.
        page = source.original(file_name).page
        url = Literal(annotation(element, "url") or page or required(root, "url", where), datatype=XSD.anyURI)
        path = Literal(xpath(element, parents))
        graph.add((provision, RDF.type, LGO.Provision))
        graph.add((provision, ELI.is_part_of, act))
        graph.add((provision, LGO.citation, Literal(required(element, "citation", where))))
        graph.add((provision, LGO.sourceUrl, url))
        graph.add((provision, LGO.sourceDocument, document))
        graph.add((provision, LGO.sourceElement, path))
        graph.add((provision, LGO.reviewStatus, LGV.SourceChecked))
        for role, (namespace, predicate) in (ROLE_PREDICATES | LINK_PREDICATES).items():
            for target in (annotation(element, role) or "").split():
                graph.add((provision, predicate, namespace[target]))
        for item in element.iter():
            for concept in (annotation(item, "requires") or "").split():
                graph.add((provision, LGO.requiresDisclosureOf, LGV[concept]))
            if item is not element:
                for concept in (annotation(item, "defines") or "").split():
                    graph.add((provision, LGO.defines, LGV[concept]))

        quote = LG[f"{provision.removeprefix(str(LG))}-q1"]
        retrieved = source.original(file_name).retrieved_on.isoformat()
        graph.add((quote, RDF.type, LGO.Quote))
        graph.add((quote, LGO.quoteOf, provision))
        graph.add((quote, LGO.text, Literal(render(element), lang=lang)))
        graph.add((quote, LGO.sourceUrl, url))
        graph.add((quote, LGO.retrievedOn, Literal(retrieved, datatype=XSD.date)))
        graph.add((quote, LGO.officialLanguageVersion, Literal(source.original(file_name).authentic)))
        graph.add((quote, LGO.sourceDocument, document))
        graph.add((quote, LGO.sourceElement, path))

        # The same provision in the other official languages: the same element in each parallel
        # text — matched by position for official XML, by lga:provision for an authored translation.
        for original in source.parallels:
            language = source.language_of(original)
            tree = parallel_roots[original.file.name]
            if original.annotated is not None:
                match = next(
                    (
                        e
                        for e in provision_elements(tree)
                        if annotation(e, "provision") == annotation(element, "provision")
                    ),
                    None,
                )
                if match is None:
                    continue  # no official version in this language: a translation is required instead
                version_url = annotation(match, "url") or original.page or url
                version_path = Literal(xpath(match, parallel_parents[original.file.name]))
            else:
                match = element_at(tree, str(path))
                if match is None:
                    raise SourceError(f"{original.file.name}: no element at {path}; run `legalgraph sources verify`")
                version_url = annotation(element, "url") or original.page or url
                version_path = path
            version = LG[f"{quote.removeprefix(str(LG))}-{language}"]
            graph.add((version, RDF.type, LGO.Quote))
            graph.add((version, LGO.quoteOf, provision))
            graph.add((version, LGO.languageVersionOf, quote))
            graph.add((version, LGO.text, Literal(render(match), lang=language)))
            graph.add((version, LGO.sourceUrl, Literal(version_url, datatype=XSD.anyURI)))
            graph.add((version, LGO.retrievedOn, Literal(original.retrieved_on.isoformat(), datatype=XSD.date)))
            graph.add((version, LGO.officialLanguageVersion, Literal(original.authentic)))
            graph.add((version, LGO.sourceDocument, documents[original.file.name]))
            graph.add((version, LGO.sourceElement, version_path))

    # Cross-references inside an EU act, read mechanically from the English text ("point (f) of
    # Article 6(1)", "Articles 13 and 14", "paragraph 2"), to the provisions of the act in the graph.
    if local(root.tag) in ("ACT", "CONS.ACT") and lang == "en":
        provisions = {str(s) for s in graph.subjects(RDF.type, LGO.Provision)}
        for provision in sorted(provisions):
            quote = graph.value(URIRef(f"{provision}-q1"), LGO.text)
            own = re.search(r"-art(\d+)", provision)
            for target in internal_references(str(quote), str(act), own.group(1) if own else None):
                if target != provision and target in provisions:
                    graph.add((URIRef(provision), LGO.refersTo, URIRef(target)))

    comment = (
        f"Generated by `legalgraph sources extract` from {where}. Do not edit:\n"
        "change the annotations in the source and run the command again."
    )
    return serialize(graph, comment)


# --- Reading view (for the site) ---------------------------------------------------------

READING_ROLES = ("citation", *PROVISION_ROLES, *LINK_PREDICATES)


def has_annotations(element: ET.Element) -> bool:
    return any(annotation_names(node) for node in element.iter())


def formatted_xml(annotated: bytes, path: str) -> str:
    """The element at `path` (an XPath from xpath()) as indented XML, for reading, with the file's own
    namespace prefixes. The file itself is never reformatted."""
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    document = etree.fromstring(annotated, parser)
    steps = [re.fullmatch(r"([^\[]+)(\[\d+\])?", step) for step in path.strip("/").split("/")]
    expression = "/" + "/".join(f"*[local-name()='{m.group(1)}']{m.group(2) or ''}" for m in steps if m)
    element = copy.deepcopy(document.xpath(expression)[0])
    etree.indent(element, space="  ")
    return etree.tostring(element, encoding="unicode", pretty_print=True).rstrip()


# Elements shown as one section of a reading page: a § (gesetze-im-internet.de, authored XML), an
# article or recital (Formex), a regulation or section (legislation.gov.uk), a CFR section (eCFR), the
# operative part or a group of grounds of a judgment. A provision's section is its nearest one.
CONTAINERS = {
    "norm",
    "section",
    "ARTICLE",
    "article",
    "CONSID",
    "ANNEX",
    "CONS.ANNEX",
    "P1",
    "Schedule",
    "DIV8",
    "SECTION",
    "JURISDICTION",
    "GR.SEQ",
}
HEADINGS = {
    "Number",
    "TitleBlock",
    "Reference",
    "TI.ART",
    "STI.ART",
    "Pnumber",
    "Title",
    "HEAD",
    "INTRO",
    "TITLE",
    "metadaten",
    "SECTNO",
    "SUBJECT",
    "num",
    "heading",
}


def reading_units(container: ET.Element) -> list[ET.Element]:
    """The parts of a section shown one by one: its paragraphs, or, where provisions sit deeper (the
    numbered definitions of Article 4 GDPR, the points of a ruling), each of them on its own."""
    if annotation(container, "provision"):
        return [container]
    if local(container.tag) == "norm":
        content = container.find("textdaten/text/Content")
        units: list[ET.Element] = []
        for child in content if content is not None else []:
            nested = any(annotation(node, "provision") for node in child.iter() if node is not child)
            if nested and not annotation(child, "provision"):  # a provision on a numbered item (UWG Anhang)
                outer = next(child.iter("DL"), None)  # its outermost list: numbers and items in turn
                units += list(outer) if outer is not None else [child]
            else:
                units.append(child)
        return units
    if container.tag == f"{{{LAW_NS}}}section":
        return container.findall(f"{{{LAW_NS}}}paragraph")
    units = []
    for child in container:
        if local(child.tag) in HEADINGS:
            continue
        nested = any(annotation(node, "provision") for node in child.iter() if node is not child)
        if nested and not annotation(child, "provision"):
            units += reading_units(child)
        else:
            units.append(child)
    return units


def heading(container: ET.Element, parents: dict[ET.Element, ET.Element]) -> tuple[str, str | None]:
    """Number and title of a section, as the document gives them."""

    def text(path: str) -> str | None:
        found = container.find(path)
        return render(found) if found is not None else None

    name = local(container.tag)
    if name == "norm":  # "§ 1"; within an article of an act numbered by articles, "Art 246a § 1"
        number, part = text("metadaten/enbez") or "", text("metadaten/gliederungseinheit/gliederungsbez")
        if part and part.startswith("Art ") and number.startswith("§"):
            number = f"{part} {number}"
        return number, text("metadaten/titel")
    if container.tag == f"{{{LAW_NS}}}section":
        return container.get("num", ""), container.get("title")
    if name == "article":  # Akoma Ntoso (Fedlex)
        return text(f"{{{AKN_NS}}}num") or "", text(f"{{{AKN_NS}}}heading")
    if name == "ARTICLE":
        return text("TI.ART") or "", text("STI.ART")
    if name == "CONSID":
        return f"Recital {re.sub(r'[^0-9]', '', text('NP/NO.P') or '')}", None
    if name in ("ANNEX", "CONS.ANNEX"):
        return text("TITLE/TI") or "Annex", text("TITLE/STI")
    if name == "P1":
        kind = (container.get("DocumentURI") or "/section/").rstrip("/").split("/")[-2]
        number = collapse("".join(container.find(f"{{{CLML_NS}}}Pnumber").itertext()))
        group = parents.get(container)
        title = group.find(f"{{{CLML_NS}}}Title") if group is not None else None
        return f"{kind.capitalize()} {number}", None if title is None else collapse("".join(title.itertext()))
    if name == "DIV8":
        head = text("HEAD") or ""
        number, _, title = head.partition(" ") if not head.startswith("§") else head.partition(" ")[2].partition(" ")
        return (f"§ {number}" if head.startswith("§") else number), title.rstrip(".") or None
    if name == "Schedule":  # legislation.gov.uk
        number = container.find(f"{{{CLML_NS}}}Number")
        title = container.find(f"{{{CLML_NS}}}TitleBlock/{{{CLML_NS}}}Title")
        return (
            collapse("".join(number.itertext())) if number is not None else "Schedule",
            collapse("".join(title.itertext())) if title is not None else None,
        )
    if name == "SECTION":  # official CFR XML (govinfo)
        return text("SECTNO") or "", (text("SUBJECT") or "").rstrip(".") or None
    if name == "JURISDICTION":
        return "Operative part", text("INTRO")
    if name == "GR.SEQ":
        return text("TITLE/TI") or "Grounds", None
    return name, None


def containing_section(element: ET.Element, parents: dict[ET.Element, ET.Element]) -> ET.Element | None:
    node: ET.Element | None = element
    while node is not None:
        if local(node.tag) in CONTAINERS:
            return node
        node = parents.get(node)
    return None


def reading_view(source: Source) -> list[dict[str, object]]:
    """The annotated sections of a source (a § or article each), paragraph by paragraph and line by
    line, with their annotations and the section's XML. Unannotated sections are left out. Provisions
    carry the same lines in each parallel language version."""
    annotated = source.annotated.read_bytes()
    root = ET.fromstring(annotated)
    parents = {child: parent for parent in root.iter() for child in parent}
    parallels = [
        (original, source.language_of(original), ET.fromstring((original.annotated or original.file).read_bytes()))
        for original in source.parallels
    ]
    containers: list[ET.Element] = []
    for element in root.iter():
        if element is not root and annotation_names(element):
            container = containing_section(element, parents)
            if container is not None and container not in containers:
                containers.append(container)

    def versions(element: ET.Element) -> dict[str, list[str]]:
        found = {}
        for original, language, other in parallels:
            if original.annotated is not None:  # an authored translation: same provision, anywhere
                match = next(
                    (
                        e
                        for e in provision_elements(other)
                        if annotation(e, "provision") == annotation(element, "provision")
                    ),
                    None,
                )
            else:
                match = element_at(other, xpath(element, parents))
            if match is not None:
                found[language] = [line.text for line in render_lines(match)]
        return found

    sections = []
    for container in containers:
        number, title = heading(container, parents)
        titles = {}
        for _original, language, other in parallels:
            match = element_at(other, xpath(container, parents))
            if match is not None and local(match.tag) == "ARTICLE" and (found := match.find("STI.ART")) is not None:
                titles[language] = render(found)
        file_name = container.get("source") if container.tag == f"{{{LAW_NS}}}section" else source.texts[0].file.name
        sections.append(
            {
                "num": number,
                "title": title,
                "titles": titles,
                "source": file_name or "",
                "xpath": xpath(container, parents),
                "xml": formatted_xml(annotated, xpath(container, parents)),
                "paragraphs": [
                    {
                        "xpath": xpath(paragraph, parents),
                        "provision": annotation(paragraph, "provision"),
                        "annotations": {
                            role: value for role in READING_ROLES if (value := annotation(paragraph, role))
                        },
                        "lines": [
                            {"text": line.text, "requires": line.requires, "defines": line.defines}
                            for line in render_lines(paragraph)
                        ],
                        "versions": versions(paragraph) if annotation(paragraph, "provision") else {},
                    }
                    for paragraph in reading_units(container)
                    if render_lines(paragraph)  # an empty element (a bare list wrapper) shows nothing
                ],
            }
        )
    return sections


# --- Link-only references ----------------------------------------------------------------
# Someone else's writing (news, law-firm summaries, enforcement databases) is not kept in sources/:
# sources/link-only.yaml lists the page, why it is only linked, the claim it backs up and at most
# one short verbatim excerpt. `extract` turns it into lgo:ExternalReference resources.

LINK_ONLY_FIELDS = {"id", "title", "publisher", "url", "date", "why_link_only", "quote", "claim", "supports"}


def extract_link_only(path: Path = LINK_ONLY) -> str | None:
    """Turtle for sources/link-only.yaml, or None when there is no such file."""
    if not path.exists():
        return None
    where = repo_path(path)
    entries = yaml.safe_load(path.read_text()) or []
    graph = Graph()
    seen: set[str] = set()
    for number, entry in enumerate(entries, 1):
        unknown = set(entry) - LINK_ONLY_FIELDS
        if unknown:
            raise SourceError(f"{where}: entry {number}: unknown field(s) {', '.join(sorted(unknown))}")
        try:
            identifier = entry["id"]
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", identifier):
                raise SourceError(f"{where}: id {identifier!r}: use lowercase letters, digits and hyphens")
            if identifier in seen:
                raise SourceError(f"{where}: id {identifier!r} appears twice")
            seen.add(identifier)
            node = LG[f"ref-{identifier}"]
            graph.add((node, RDF.type, LGO.ExternalReference))
            graph.add((node, DCTERMS.title, Literal(entry["title"])))
            graph.add((node, DCTERMS.publisher, Literal(entry["publisher"])))
            graph.add((node, LGO.sourceUrl, Literal(entry["url"], datatype=XSD.anyURI)))
            graph.add((node, LGO.linkOnlyReason, Literal(entry["why_link_only"])))
        except KeyError as error:
            raise SourceError(f"{where}: entry {number}: missing field {error}") from error
        if entry.get("date"):
            graph.add((node, DCTERMS.date, Literal(str(entry["date"]), datatype=XSD.date)))
        if entry.get("claim"):
            graph.add((node, RDFS.comment, Literal(entry["claim"], lang="en")))
        for target in entry.get("supports") or []:
            graph.add((node, LGO.supports, LG[target]))
        if quote := entry.get("quote"):
            text = collapse(str(quote.get("text", "")))
            if not text or not quote.get("locator") or not quote.get("language"):
                raise SourceError(f"{where}: {identifier}: a quote needs text, locator and language")
            if len(text) > EXCERPT_LIMIT:
                raise SourceError(
                    f"{where}: {identifier}: the quote has {len(text)} characters; someone else's work is quoted"
                    f" in at most {EXCERPT_LIMIT} (one or two sentences), or linked"
                )
            graph.add((node, LGO.excerpt, Literal(text, lang=quote["language"])))
            graph.add((node, LGO.excerptLocator, Literal(str(quote["locator"]))))
    comment = (
        f"Generated by `legalgraph sources extract` from {where}. Do not edit:\n"
        "change the list and run the command again."
    )
    return serialize(graph, comment)
