"""Number and title of a section of a reading page, as each XML dialect gives them."""

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable

from legalgraph.sources.constants import AKN_NS, CLML_NS, LAW_NS
from legalgraph.sources.render import render
from legalgraph.sources.text import collapse
from legalgraph.sources.tree import Parents, local

Heading = tuple[str, str | None]


def text(container: ET.Element, path: str) -> str | None:
    found = container.find(path)
    return render(found) if found is not None else None


def all_text(element: ET.Element) -> str:
    return collapse("".join(element.itertext()))


def norm(container: ET.Element, _parents: Parents) -> Heading:
    """ "§ 1"; within an article of an act numbered by articles, "Art 246a § 1"."""
    number, part = (
        text(container, "metadaten/enbez") or "",
        text(container, "metadaten/gliederungseinheit/gliederungsbez"),
    )
    if part and part.startswith("Art ") and number.startswith("§"):
        number = f"{part} {number}"
    return number, text(container, "metadaten/titel")


def akoma_ntoso_article(container: ET.Element, _parents: Parents) -> Heading:
    return text(container, f"{{{AKN_NS}}}num") or "", text(container, f"{{{AKN_NS}}}heading")


def formex_article(container: ET.Element, _parents: Parents) -> Heading:
    return text(container, "TI.ART") or "", text(container, "STI.ART")


def recital(container: ET.Element, _parents: Parents) -> Heading:
    return f"Recital {re.sub(r'[^0-9]', '', text(container, 'NP/NO.P') or '')}", None


def annex(container: ET.Element, _parents: Parents) -> Heading:
    return text(container, "TITLE/TI") or "Annex", text(container, "TITLE/STI")


def uk_provision(container: ET.Element, parents: Parents) -> Heading:
    """legislation.gov.uk: "Regulation 6" or "Section 2", titled by its group."""
    kind = (container.get("DocumentURI") or "/section/").rstrip("/").split("/")[-2]
    number_element = container.find(f"{{{CLML_NS}}}Pnumber")
    number = all_text(number_element) if number_element is not None else ""
    group = parents.get(container)
    title = group.find(f"{{{CLML_NS}}}Title") if group is not None else None
    return f"{kind.capitalize()} {number}", None if title is None else all_text(title)


def us_code_section(container: ET.Element, _parents: Parents) -> Heading:
    head = text(container, "HEAD") or ""
    if head.startswith("§"):
        number, _, title = head.partition(" ")[2].partition(" ")
        return f"§ {number}", title.rstrip(".") or None
    number, _, title = head.partition(" ")
    return number, title.rstrip(".") or None


def uk_schedule(container: ET.Element, _parents: Parents) -> Heading:
    number = container.find(f"{{{CLML_NS}}}Number")
    title = container.find(f"{{{CLML_NS}}}TitleBlock/{{{CLML_NS}}}Title")
    return all_text(number) if number is not None else "Schedule", all_text(title) if title is not None else None


def cfr_section(container: ET.Element, _parents: Parents) -> Heading:
    """Official CFR XML (govinfo)."""
    return text(container, "SECTNO") or "", (text(container, "SUBJECT") or "").rstrip(".") or None


READERS: dict[str, Callable[[ET.Element, Parents], Heading]] = {
    "norm": norm,
    "article": akoma_ntoso_article,
    "ARTICLE": formex_article,
    "CONSID": recital,
    "ANNEX": annex,
    "CONS.ANNEX": annex,
    "P1": uk_provision,
    "DIV8": us_code_section,
    "Schedule": uk_schedule,
    "SECTION": cfr_section,
    "JURISDICTION": lambda container, _: ("Operative part", text(container, "INTRO")),
    "GR.SEQ": lambda container, _: (text(container, "TITLE/TI") or "Grounds", None),
}


def heading(container: ET.Element, parents: Parents) -> Heading:
    if container.tag == f"{{{LAW_NS}}}section":
        return container.get("num", ""), container.get("title")
    reader = READERS.get(local(container.tag))
    return reader(container, parents) if reader else (local(container.tag), None)
