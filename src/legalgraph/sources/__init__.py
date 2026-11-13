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

from legalgraph.sources.annotate import reannotate, strip_annotations
from legalgraph.sources.constants import ANNOTATION_NS, LAW_NS, LICENCES, LINK_ONLY, LINK_ONLY_OUTPUT, SOURCES_DIR
from legalgraph.sources.extract import extract
from legalgraph.sources.fetch import (
    download,
    fetch,
    fetch_saved,
    html_fragment,
    record_fetch,
    same_saved_url,
    saved_url,
)
from legalgraph.sources.link_only import extract_link_only
from legalgraph.sources.model import Original, Source, SourceError, load_sources, parse_index, repo_path, sha256
from legalgraph.sources.reading import reading_view
from legalgraph.sources.render import render, render_lines
from legalgraph.sources.text import authentic_form, same_text
from legalgraph.sources.verify import verify

__all__ = [
    "ANNOTATION_NS",
    "LAW_NS",
    "LICENCES",
    "LINK_ONLY",
    "LINK_ONLY_OUTPUT",
    "SOURCES_DIR",
    "Original",
    "Source",
    "SourceError",
    "authentic_form",
    "download",
    "extract",
    "extract_link_only",
    "fetch",
    "fetch_saved",
    "html_fragment",
    "load_sources",
    "parse_index",
    "reading_view",
    "reannotate",
    "record_fetch",
    "render",
    "render_lines",
    "repo_path",
    "same_saved_url",
    "same_text",
    "saved_url",
    "sha256",
    "strip_annotations",
    "verify",
]
