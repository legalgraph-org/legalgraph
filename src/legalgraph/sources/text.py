"""Text as compared word for word: an original's words, normalised the same way on both sides."""

import functools
import io
import logging
import re
import unicodedata

from bs4 import BeautifulSoup
from pypdf import PdfReader

from legalgraph.sources.model import Original

# pypdf logs notices about some PDFs' font encodings; the text check does not depend on them.
logging.getLogger("pypdf").setLevel(logging.CRITICAL)


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


def original_full_text(original: Original) -> str:
    """The original's text as the portal serves it, including the editorial notes text_ignore
    removes for the word check."""
    return collapse(BeautifulSoup(original.file.read_bytes(), "html.parser").get_text(" "))


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
    text = re.sub(r"[‒–—―−]", "-", text)
    text = re.sub(r"(?<=[^\W\d_])\(\d{1,3}\)", "", text)
    if media_type != "application/pdf":
        # An inline element (a linked defined term) ending before a comma leaves a space there.
        return collapse(re.sub(r"\s+(?=[,.;:)])", "", text))
    return re.sub(r"[\s\-­‐‑]+", "", unicodedata.normalize("NFKC", text))


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
