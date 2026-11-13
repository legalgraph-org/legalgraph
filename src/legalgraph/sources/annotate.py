"""The lga: attributes of an annotated official XML: removing them, and carrying them onto a newer
original of the same text."""

import re
import xml.parsers.expat
import xml.sax.saxutils
from dataclasses import dataclass, field

from legalgraph.sources.constants import ANNOTATION_NS, STRIP_PATTERNS

Path = tuple[tuple[str, int], ...]  # each element's tag and sibling index, from the root down


def strip_annotations(annotated: bytes) -> bytes:
    for pattern in STRIP_PATTERNS:
        annotated = pattern.sub(b"", annotated)
    return annotated


@dataclass
class Elements:
    """For every element of an XML file: where its start tag ends, its lga:* attributes, and its text."""

    ends: dict[Path, int] = field(default_factory=dict)
    annotations: dict[Path, dict[str, str]] = field(default_factory=dict)
    texts: dict[Path, list[str]] = field(default_factory=dict)

    def text(self, path: Path) -> str:
        return re.sub(r"\s+", " ", "".join(self.texts.get(path, []))).strip()


def start_tag_end(data: bytes, offset: int) -> int:
    """The offset of the ">" closing a start tag, skipping any ">" inside quoted attribute values."""
    while True:
        end = data.index(b">", offset)
        inside = data[offset:end]
        if inside.count(b'"') % 2 == 0 and inside.count(b"'") % 2 == 0:
            return end
        offset = end + 1


def walk_elements(data: bytes) -> Elements:
    """All elements of the XML, from one expat walk."""
    found = Elements()
    stack: list[tuple[str, int]] = []
    counts: dict[tuple, int] = {}
    parser = xml.parsers.expat.ParserCreate()

    def start(tag: str, attrs: dict[str, str]) -> None:
        sibling = (*stack, tag)
        counts[sibling] = counts.get(sibling, 0) + 1
        stack.append((tag, counts[sibling]))
        if lga := {k: v for k, v in attrs.items() if k.startswith("lga:")}:
            found.annotations[tuple(stack)] = lga
        found.ends[tuple(stack)] = start_tag_end(data, parser.CurrentByteIndex)

    def end(_tag: str) -> None:
        stack.pop()

    def chars(text: str) -> None:
        # An element's text is its own and its descendants' — collect against every prefix path.
        for depth in range(1, len(stack) + 1):
            found.texts.setdefault(tuple(stack[:depth]), []).append(text)

    parser.StartElementHandler, parser.EndElementHandler, parser.CharacterDataHandler = start, end, chars
    parser.Parse(data, True)
    return found


def attribute_text(attributes: dict[str, str]) -> str:
    """Double-quoted and escaped, as strip_annotations() expects: expat handed the values back unescaped."""
    return "".join(f' {k}="{xml.sax.saxutils.escape(v, {chr(34): "&quot;"})}"' for k, v in attributes.items())


def reannotate(old_annotated: bytes, new_original: bytes) -> tuple[bytes, list[str]]:
    """Carry every lga: attribute of the old annotated XML onto the new original, byte-exact.

    Each annotated element is addressed by its path (tag + sibling index); elements whose text
    changed since annotation are reported and left unannotated rather than quoting wrong text.
    """
    old, new = walk_elements(old_annotated), walk_elements(new_original)
    annotations = old.annotations
    root = next(iter(new.ends), None)
    if annotations and root is not None and root not in annotations:
        annotations = {root: {}, **annotations}  # the root declares xmlns:lga even when it has no lga: attributes
    problems, inserts = [], []
    for path, attributes in annotations.items():
        if path not in new.ends:
            problems.append(f"<{path[-1][0]}>: element no longer exists")
            continue
        if old.text(path) != new.text(path) and len(path) > 1:
            problems.append(f"<{path[-1][0]}>: text changed, annotation left out")
            continue
        root_namespace = {"xmlns:lga": ANNOTATION_NS} if len(path) == 1 else {}  # the root also carries xmlns:lga
        end = new.ends[path]
        self_closing = 1 if new_original[end - 1 : end] == b"/" else 0
        inserts.append((end - self_closing, attribute_text({**root_namespace, **attributes})))
    out = new_original
    for offset, text in sorted(inserts, reverse=True):
        out = out[:offset] + text.encode() + out[offset:]
    return out, problems
