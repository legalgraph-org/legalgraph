"""Places in a Formex text (the EU Official Journal), for matching what corrigenda and amending acts
change: an article and its paragraph or point, a recital, or an annex and its point."""

import re
import xml.etree.ElementTree as ET

from legalgraph.sources.model import Original
from legalgraph.sources.text import collapse
from legalgraph.sources.tree import Parents, local

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


def annex_place(node: ET.Element, sub: str | None) -> Place:
    title = node.find("TITLE/TI")
    numeral = re.search(r"\b([IVX]+)\b", collapse("".join(title.itertext()))) if title is not None else None
    return "annex", numeral.group(1) if numeral else "I", sub


def paragraph_number(node: ET.Element) -> str:
    return str(int(re.sub(r"\D", "", node.get("IDENTIFIER", "").split(".")[-1]) or 0))


def formex_place(element: ET.Element, parents: Parents) -> Place | None:
    """Where an element of a Formex text is, walking up from it to its article, recital or annex."""
    sub: str | None = None
    node: ET.Element | None = element
    while node is not None:
        name = local(node.tag)
        if name == "CONSID":
            number = re.sub(r"\D", "", point_label(node))
            return ("rec", number.lstrip("0"), None) if number else None
        if name == "ARTICLE" and node.get("IDENTIFIER"):
            return "art", article_number(node.get("IDENTIFIER", "")), sub
        if name in ("ANNEX", "CONS.ANNEX"):  # an annex, in an Official Journal or a consolidated text
            return annex_place(node, sub)
        if name == "PARAG" and node.get("IDENTIFIER"):
            sub = paragraph_number(node)
        elif name == "ITEM" and sub is None and (label := point_label(node)):
            sub = label
        node = parents.get(node)
    return None


def changed_place(place: str) -> Place | None:
    if place == "Whole text":  # a correction applied throughout ("Gesamter Text")
        return ("all", "", None)
    match = CHANGED_PLACE.match(place)
    if not match:
        return None
    if match.group(3):
        return ("rec", match.group(3).lstrip("0"), None)
    if match.group(4):
        return ("annex", match.group(4), match.group(5).lower() if match.group(5) else None)
    return ("art", match.group(1).lower(), match.group(2))


def changed_places(original: Original) -> list[Place]:
    return [place for entry in original.corrects if (place := changed_place(entry)) is not None]


def covers(change: Place, place: Place) -> bool:
    if change[0] == "all":
        return True
    return change[:2] == place[:2] and (change[2] is None or place[2] in (None, change[2]))


def point_number(element: ET.Element) -> str | None:
    number = element.find("NP/NO.P")
    return collapse("".join(number.itertext())) if number is not None else None


def formex_key(element: ET.Element, parents: Parents) -> list[tuple[str, str]]:
    """How to find the same element in another Formex text of the act: its ARTICLE and PARAG
    identifiers, ITEM numbers and recital number, outermost first."""
    key = []
    node: ET.Element | None = element
    while node is not None:
        name = local(node.tag)
        if name in ("ARTICLE", "PARAG") and node.get("IDENTIFIER"):
            key.append((name, node.get("IDENTIFIER", "")))
        elif name in ("ITEM", "CONSID") and (number := point_number(node)) is not None:
            key.append((name, number))
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
            scope = next((e for e in scope.iter(name) if point_number(e) == value), None)
    return scope
