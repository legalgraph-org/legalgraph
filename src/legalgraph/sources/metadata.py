"""Title, short name, date and status notes of an act, from the document's own metadata, one reader
per XML dialect."""

import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field

from legalgraph.sources.constants import AKN_NS, LAW_NS
from legalgraph.sources.render import render
from legalgraph.sources.text import collapse
from legalgraph.sources.tree import local


@dataclass
class ActMetadata:
    title: str | None = None
    short: str | None = None
    issued: str | None = None
    notes: list[str] = field(default_factory=list)


def first(element: ET.Element | None) -> str | None:
    return render(element) if element is not None else None


def iso_date(element: ET.Element | None) -> str | None:
    iso = element.get("ISO", "") if element is not None else ""
    return f"{iso[:4]}-{iso[4:6]}-{iso[6:]}" if len(iso) == 8 else None


def title_lines(title: ET.Element | None) -> list[str]:
    return [render(paragraph) for paragraph in title.iterfind("P")] if title is not None else []


def formex_act(root: ET.Element) -> ActMetadata:
    """Formex: title from the act itself, date of signature."""
    act = local(root.tag) == "ACT"
    title = root.find("TITLE/TI") if act else root.find("CONS.DOC/FAM.COMP/BIB.DATA/TITLE/TI")
    lines = title_lines(title)
    if len(lines) > 1 and lines[-1].startswith("(") and lines[-1].endswith(")"):
        lines = lines[:-1]  # a last line wholly in brackets is the "(Text with EEA relevance)" note
    signed = root.find("BIB.INSTANCE/DATE") if act else title.find(".//DATE") if title is not None else None
    return ActMetadata(" ".join(lines) or None, issued=iso_date(signed))


def formex_judgment(root: ET.Element) -> ActMetadata:
    """Formex judgment: "Judgment of the Court (Grand Chamber) of 1 October 2019, Planet49, C-673/17"."""
    title = root.find("TITLE/TI")
    case = root.find("BIB.JUDGMENT/REF.CASE/NO.CASE")
    names = root.findall("CURR.TITLE/PAGE.HEADER/P")
    parts = [
        " of ".join(title_lines(title)),
        render(names[-1]) if names else "",
        render(case) if case is not None else "",
    ]
    issued = iso_date(title.find(".//DATE") if title is not None else None)
    return ActMetadata(", ".join(part for part in parts if part) or None, issued=issued)


def akoma_ntoso(root: ET.Element) -> ActMetadata:
    """Akoma Ntoso (Fedlex): the work's name in the document's language."""
    akn = f"{{{AKN_NS}}}"
    work = root.find(f".//{akn}FRBRWork")
    language = root.find(f".//{akn}FRBRExpression/{akn}FRBRlanguage")
    code = {"deu": "de", "fra": "fr", "ita": "it", "eng": "en", "roh": "rm"}.get(
        language.get("language", "") if language is not None else "", "de"
    )
    names = list(work.iterfind(f"{akn}FRBRname")) if work is not None else []
    own = next((n for n in names if n.get("{http://www.w3.org/XML/1998/namespace}lang") == code), None)
    dates = work.iterfind(f"{akn}FRBRdate") if work is not None else iter([])
    dated = next((d for d in dates if d.get("name") == "jolux:dateDocument"), None)
    return ActMetadata(
        own.get("value") if own is not None else None,
        own.get("shortForm") if own is not None else None,
        dated.get("date") if dated is not None else None,
    )


def legislation_gov_uk(root: ET.Element) -> ActMetadata:
    """legislation.gov.uk: title from the metadata, date made."""
    dc = "{http://purl.org/dc/elements/1.1/}"
    ukm = "{http://www.legislation.gov.uk/namespaces/metadata}"
    title = root.find(f"{ukm}Metadata/{dc}title")
    made = root.find(f".//{ukm}Made")
    return ActMetadata(
        collapse(title.text or "") if title is not None else None,
        issued=made.get("Date") if made is not None else None,
    )


def authored(root: ET.Element) -> ActMetadata:
    """Our own schema: <meta> with title, short name and date."""
    meta = root.find(f"{{{LAW_NS}}}meta")
    if meta is None:
        return ActMetadata()
    law = f"{{{LAW_NS}}}"
    return ActMetadata(first(meta.find(f"{law}title")), first(meta.find(f"{law}short")), first(meta.find(f"{law}date")))


def gesetze_im_internet(root: ET.Element) -> ActMetadata:
    """gesetze-im-internet.de: the metadata of the first norm, with its status notes."""
    metadata = root.find("norm/metadaten")
    if metadata is None:
        return ActMetadata()
    short = metadata.find("amtabk")
    if short is None:
        short = metadata.find("jurabk")
    notes = [render(note) for note in metadata.iterfind("standangabe/standkommentar")]
    return ActMetadata(first(metadata.find("langue")), first(short), first(metadata.find("ausfertigung-datum")), notes)


READERS: dict[str, Callable[[ET.Element], ActMetadata]] = {
    "ACT": formex_act,
    "CONS.ACT": formex_act,
    "JUDGMENT": formex_judgment,
    "akomaNtoso": akoma_ntoso,
    "Legislation": legislation_gov_uk,
    "law": authored,
}


def act_metadata(root: ET.Element) -> ActMetadata:
    return READERS.get(local(root.tag), gesetze_im_internet)(root)
