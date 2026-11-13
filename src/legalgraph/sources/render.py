"""The text of an element as a reader sees it, line by line, by fixed rules for every XML dialect read.

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

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from legalgraph.sources.text import collapse
from legalgraph.sources.tree import annotation, local

SKIPPED = {"FnR", "NOTE", "CommentaryRef", "FootnoteRef", "authorialNote"}
BLOCKS = {"ITEM", "ALINEA", "P2", "P3", "P4", "P5"}
NUMBERS = {"NO.PARAG", "NO.P", "Pnumber", "num"}  # num: Akoma Ntoso (Fedlex)
LISTS = {"DL", "list", "LIST"}
LINE_ANNOTATIONS = ("requires", "defines")
NOTE_MARK = "⁣"  # where a footnote mark of an authored text sits, for the word check only


@dataclass
class Line:
    text: str
    requires: list[str] = field(default_factory=list)
    defines: list[str] = field(default_factory=list)


@dataclass
class PendingLine:
    chunks: list[str] = field(default_factory=list)
    prefix: list[str] = field(default_factory=list)  # the numbers the line starts with
    annotations: dict[str, list[str]] = field(default_factory=lambda: {key: [] for key in LINE_ANNOTATIONS})


def starts_block(name: str, parent: str) -> bool:
    return (
        name in BLOCKS
        or (name == "P" and parent in ("ALINEA", "DIV8", "SECTION"))
        or (name == "p" and parent == "content")
        or (name == "Text" and parent.endswith("para"))
    )


def number_text(node: ET.Element, name: str, parent: str) -> str:
    value = collapse("".join(node.itertext()))
    if name != "Pnumber":
        return value
    return f"{value}." if parent == "P1" else f"({value})"


class LineRenderer:
    """Walks an element and collects its lines; `marks` keeps footnote positions for the word check."""

    def __init__(self, marks: bool) -> None:
        self.marks = marks
        self.lines: list[PendingLine] = [PendingLine()]

    def newline(self) -> None:
        self.lines.append(PendingLine())

    def text(self, value: str | None) -> None:
        if value:
            self.lines[-1].chunks.append(re.sub(r"\s+", " ", value))

    def soft_break(self) -> None:
        """New line, unless the current one is empty or holds only a number."""
        current = collapse("".join(self.lines[-1].chunks))
        if current and current != collapse(" ".join(self.lines[-1].prefix)):
            self.newline()

    def leaf(self, node: ET.Element, name: str) -> bool:
        """Elements whose content is not text: skipped, or replaced by one character."""
        if name in SKIPPED:
            return True
        if name in ("note", "page"):  # footnote mark or page break in authored XML: not part of the text
            if self.marks:
                self.text(NOTE_MARK)
            return True
        if name in ("QUOT.START", "QUOT.END"):
            self.text(chr(int(node.get("CODE", "22"), 16)))
            return True
        return False

    def open(self, node: ET.Element, name: str, parent: str) -> None:
        """Where an element starts: a new line, a space, or its number."""
        if name in ("DT", "BR", "br"):
            self.newline()
        elif name == "DD":
            self.text(" ")
        elif name == "item" and node.get("num") is not None:  # authored XML; Akoma Ntoso items have <num>
            self.newline()
            self.text(f"{node.get('num', '')} ")
        elif name == "paragraph" and node.get("num"):
            self.text(f"{node.get('num')} ")
        elif name == "item" or starts_block(name, parent):
            self.soft_break()

    def walk(self, node: ET.Element, parent: str) -> None:
        name = local(node.tag)
        if self.leaf(node, name):
            return
        self.open(node, name, parent)
        for key in LINE_ANNOTATIONS:
            self.lines[-1].annotations[key].extend((annotation(node, key) or "").split())
        if name in NUMBERS:
            value = number_text(node, name, parent)
            self.text(f"{value} ")
            self.lines[-1].prefix.append(value)
            return
        self.text(node.text)
        previous = None
        for child in node:
            if previous == "LA" and local(child.tag) == "LA":
                self.text(" ")  # two text blocks of one item (gesetze-im-internet.de): a heading and its text
            self.walk(child, name)
            if local(child.tag) in LISTS:
                self.newline()
            self.text(child.tail)
            previous = local(child.tag)

    def result(self) -> list[Line]:
        result: list[Line] = []
        carried: dict[str, list[str]] = {key: [] for key in LINE_ANNOTATIONS}
        for entry in self.lines:
            line = re.sub(r" +", " ", "".join(entry.chunks)).strip()
            if line:
                merged = {key: carried[key] + entry.annotations[key] for key in LINE_ANNOTATIONS}
                result.append(Line(line, merged["requires"], merged["defines"]))
                carried = {key: [] for key in LINE_ANNOTATIONS}
            else:
                for key in LINE_ANNOTATIONS:
                    carried[key] += entry.annotations[key]  # an annotation on an element that starts with an empty line
        return result


def render_lines(element: ET.Element, marks: bool = False) -> list[Line]:
    """The lines of an element, with the item annotations (lga:requires, lga:defines) of each."""
    renderer = LineRenderer(marks)
    renderer.walk(element, "")
    return renderer.result()


def render(element: ET.Element) -> str:
    """The text of an element as one string, one line per paragraph or list item (see render_lines)."""
    return "\n".join(line.text for line in render_lines(element))
