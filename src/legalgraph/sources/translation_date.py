"""An official translation older than the provision it translates must not stand as its English.

The original marks each amendment with an editorial note (`{… Законом № … від DD.MM.YYYY}`) — inside
text_ignore's elements, so it is not part of the checked words. A note dated after the parallel's
`as_of` inside, or directly after, a translated provision fails.
"""

import re
import xml.etree.ElementTree as ET
from datetime import date

from legalgraph.sources.model import Original, Source, repo_path
from legalgraph.sources.render import render_lines
from legalgraph.sources.text import comparable, original_full_text
from legalgraph.sources.tree import annotation, parents_of, provision_elements, provision_named, section_source

AMENDMENT_NOTE = re.compile(r"\{[^{}]*\}")
# zakon.rada.gov.ua dates its editorial notes "від DD.MM.YYYY" (№ of the amending act follows №).
AMENDED_ON = re.compile(r"від (\d{1,2})\.(\d{1,2})\.(\d{4})")


def provision_region(haystack: str, lines: list[str]) -> str | None:
    """The stretch of the original from a provision's first line to its last, with the notes the
    portal sets directly after it; None when the provision is not found."""
    start = haystack.find(lines[0])
    if start < 0:
        return None  # the word check reports text missing from the original
    end = haystack.find(lines[-1], start) + len(lines[-1])
    region = haystack[start:end]
    rest = haystack[end:]
    while match := re.match(r"\s*\{[^{}]*\}", rest):
        region += match.group(0)
        rest = rest[match.end() :]
    return region


def first_note_after(region: str, as_of: date) -> date | None:
    """The latest date of the first editorial note in the region that is newer than `as_of`."""
    for note in AMENDMENT_NOTE.findall(region):
        amended = [date(int(y), int(m), int(d)) for d, m, y in AMENDED_ON.findall(note)]
        if amended and max(amended) > as_of:
            return max(amended)
    return None


def verify_translation_date(source: Source, root: ET.Element, parallel: Original, p_root: ET.Element) -> list[str]:
    errors = []
    parents = parents_of(root)
    haystacks: dict[str, str] = {}
    for element in provision_elements(p_root):
        label = annotation(element, "provision")
        main = provision_named(root, label)
        if main is None:
            continue  # reported by verify_authored_parallels
        name = section_source(main, parents) if len(source.texts) > 1 else source.texts[0].file.name
        original = source.original(name)
        if original.media_type != "text/html":
            continue  # the amendment-note convention is the portal's HTML one
        haystack = haystacks.setdefault(name, comparable(original_full_text(original), original.media_type))
        lines = [comparable(line.text, original.media_type) for line in render_lines(main)]
        region = provision_region(haystack, lines) if all(lines) else None
        amended = first_note_after(region, parallel.as_of) if region is not None else None
        if amended is not None:
            errors.append(
                f"{repo_path(parallel.annotated)}: {label}: amended on {amended.isoformat()} "
                f"by a note in {name}, after the translation of {parallel.as_of.isoformat()}"
            )
    return errors
