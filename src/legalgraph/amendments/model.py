"""What a portal shows, what the graph recorded, and the verdict; with the helpers every checker uses."""

import re
import time
from dataclasses import dataclass
from datetime import date, datetime

from bs4 import BeautifulSoup

from legalgraph.sources import download

PAUSE = 0.4  # seconds between portal requests


@dataclass
class LiveAmendment:
    """What the official portal shows today."""

    citation: str | None = None  # "BGBl. I Nr. 94/2025", "S.I. 2026/1015", "Regulation (EU) 2022/2065"
    date: date | None = None  # adoption/publication date of the amending instrument, if the portal gives one
    detail: str = ""  # the portal's own wording, for the report
    repealed_by: str | None = None  # set when the portal says the act is repealed
    year: int | None = None  # when only the year is comparable (legislation.gov.uk)
    number: int | None = None  # the instrument's number within the year, when known


@dataclass
class GraphCheck:
    """The AmendmentCheck triples the graph holds for one act."""

    checked_on: date | None = None
    source_url: str | None = None
    citation: str | None = None
    amendment_date: date | None = None
    in_force: date | None = None
    current: bool | None = None
    comment: str = ""


@dataclass
class Result:
    act: str
    ok: bool
    skipped: bool
    message: str


def get(url: str, headers: dict[str, str] | None = None) -> bytes:
    time.sleep(PAUSE)
    return download(url, headers)


def page_text(page: bytes) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(page, "html.parser").get_text(" "))


def parse_date(text: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return None
