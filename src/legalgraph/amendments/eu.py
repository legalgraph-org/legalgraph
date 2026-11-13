"""EUR-Lex / Cellar: the amending and repealing acts the Publications Office records for an EU act."""

import functools
import io
import re
import xml.etree.ElementTree as ET
from datetime import date

from legalgraph.amendments.model import LiveAmendment, get, parse_date

CELLAR = "https://publications.europa.eu/resource/celex/{}"
CELLAR_NOTICE = {"Accept": "application/xml;notice=object"}
CELLAR_TREE = {"Accept": "application/xml;notice=tree"}


@functools.cache
def cellar_date(celex: str) -> date | None:
    """The WORK_DATE_DOCUMENT of a CELEX work (its adoption/signature date)."""
    try:
        root = ET.parse(io.BytesIO(get(CELLAR.format(celex), CELLAR_NOTICE))).getroot()
    except Exception:
        return None
    for work in root.findall(".//WORK"):
        cid = work.find("RESOURCE_LEGAL_ID_CELEX/VALUE")
        if cid is not None and cid.text == celex:
            value = work.find("WORK_DATE_DOCUMENT/VALUE")
            return parse_date(value.text) if value is not None and value.text else None
    return None


def link_ids(tree: str, tag: str) -> list[str]:
    return [
        inner.group(1)
        for outer in re.finditer(rf'<{tag} type="link">(.*?)</{tag}>', tree, re.S)
        for inner in re.finditer(r"<IDENTIFIER>(3[0-9A-Z()]{8,14})</IDENTIFIER>", outer.group(1))
    ]


def check_cellar(celex: str) -> LiveAmendment:
    tree = get(CELLAR.format(celex), CELLAR_TREE).decode("utf-8", "replace")
    repeal = link_ids(tree, "RESOURCE_LEGAL_REPEALED_BY_RESOURCE_LEGAL")
    if repeal:
        return LiveAmendment(detail=f"repealed by {repeal[-1]}", repealed_by=repeal[-1])
    best: tuple[date | None, str | None] = (None, None)
    for amender in link_ids(tree, "RESOURCE_LEGAL_AMENDED_BY_RESOURCE_LEGAL"):
        found = cellar_date(amender)
        if found is not None and (best[0] is None or found > best[0]):
            best = (found, amender)
    if best[1] is None:
        return LiveAmendment(detail="no AMENDED_BY relation in Cellar")
    return LiveAmendment(citation=f"CELEX {best[1]}", date=best[0], detail=f"amended by {best[1]}")


def celex_citation(citation: str) -> str:
    """How a CELEX id reads as a legal citation, e.g. 32019L2161 -> Directive (EU) 2019/2161."""
    m = re.match(r"3(\d{4})([LRD])(\d+)", citation)
    if not m:
        return citation
    kind = {"L": "Directive", "R": "Regulation", "D": "Decision"}[m.group(2)]
    return f"{kind} (EU) {m.group(1)}/{int(m.group(3))}"
