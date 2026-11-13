"""Portals outside the EU and EEA: the United Kingdom, Canada, the United States and Türkiye."""

import io
import json
import re
from datetime import datetime

from pypdf import PdfReader

from legalgraph.amendments.model import LiveAmendment, get, page_text, parse_date


def check_legislation_gov(path: str) -> LiveAmendment:
    """The latest amending instrument on the act page: anything cited as "by S.I. YYYY/NNN" or
    "by YYYY c. NN", in the outstanding-changes list or in the applied annotations."""
    page = get(f"https://www.legislation.gov.uk/{path}")
    text = page_text(page)
    detail_m = re.search(
        r"(?:is up to date with all changes known to be in force on or before [^.]+"
        r"|currently no known outstanding effects|Changes and effects yet to be applied[^.]*\.)",
        text,
    )
    best: tuple[int, int] | None = None
    # Textual amendment notes read "Words ... substituted (date) by The X Regulations 2026
    # (S.I. 2026/386)" — the amending instrument is the (S.I.) in "by" position after a
    # change verb. Commencement cites ("in force at … by S.I. …") and bare act cites don't count.
    verbs = r"(?:inserted|substituted|omitted|added|amended|repealed|modified|revoked|renumbered|applied)"
    for m in re.finditer(verbs + r"[^;]{0,400}?\bby\b[^;]{0,200}?\(S\.I\. (\d{4})/(\d+)\)", text):
        y, n = int(m.group(1)), int(m.group(2))
        if y > 2100:  # old-style "S.I. 3134/2013" writes number/year
            y, n = n, y
        if best is None or (y, n) > best:
            best = (y, n)
    for m in re.finditer(r"(\d{4}) c\. (\d+)", text):
        y, n = int(m.group(1)), int(m.group(2))
        if best is None or (y, n) > best:
            best = (y, n)
    live = LiveAmendment(detail=detail_m.group(0) if detail_m else "(no currency statement found)")
    if best:
        live.year, live.number = best
        live.citation = f"{best[0]}/{best[1]}"
    return live


def check_laws_lois(slug: str) -> LiveAmendment:
    text = page_text(get(f"https://laws-lois.justice.gc.ca/eng/acts/{slug}/"))
    m = re.search(r"last amended on (\d{4}-\d{2}-\d{2})", text, re.I)
    if m:
        return LiveAmendment(citation=f"last amended on {m.group(1)}", date=parse_date(m.group(1)), detail=m.group(0))
    return LiveAmendment(detail="no 'last amended' statement found")


def check_ecfr(title: str, part: str, section: str) -> LiveAmendment:
    url = f"https://www.ecfr.gov/api/versioner/v1/versions/title-{title}.json?part={part}&section={section}"
    data = json.loads(get(url))
    versions = [v for v in data.get("content_versions", []) if v.get("substantive")]
    if versions:
        latest = max(versions, key=lambda v: v["amendment_date"])
        return LiveAmendment(
            citation=f"version {latest['amendment_date']}",
            date=parse_date(latest["amendment_date"]),
            detail=f"eCFR {latest['identifier']} version {latest['amendment_date']}",
        )
    return LiveAmendment(detail="no versions in eCFR API")


def check_uscode(pkg: str, htm: str) -> LiveAmendment:
    page = get(f"https://www.govinfo.gov/content/pkg/{pkg}/html/{htm}.htm")
    text = page_text(page)
    m = re.search(r"Amendments\s+(.*?)(?:Statutory Notes|Cross References|Miscellaneous)", text)
    if m:
        pls = re.findall(r"Pub\. L\. [\d–-]+", m.group(1))
        return LiveAmendment(citation=pls[-1] if pls else "amendment note present", detail=m.group(1)[:200])
    return LiveAmendment(detail="no Amendments note")


def check_cppa(url: str) -> LiveAmendment:
    text = page_text(get(url))
    m = re.search(r"CCPA Regulations \(Effective ([A-Z][a-z]+ \d{1,2}, \d{4})\)", text)
    if not m:
        m = re.search(r"CCPA Regulations[^)]*Effective ([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    if m:
        when = datetime.strptime(m.group(1), "%B %d, %Y").date()
        return LiveAmendment(citation=f"effective {m.group(1)}", date=when, detail=m.group(0))
    return LiveAmendment(detail="no effective date found on CPPA page")


def check_mevzuat(act: str) -> LiveAmendment:
    pdf = get(f"https://www.mevzuat.gov.tr/mevzuatmetin/{act}.pdf")
    text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)
    changes = re.findall(r"(?:Değişik|Ek|Mülga|İptal|İhdas):\s*(\d{1,2}/\d{1,2}/\d{4})-(\d+)", text)
    if changes:
        latest = max(((parse_date(c[0]), c[1]) for c in changes if parse_date(c[0])), key=lambda t: t[0])
        return LiveAmendment(citation=f"Kanun {latest[1]}", date=latest[0], detail=f"Değişik: {latest[0]}-{latest[1]}")
    return LiveAmendment(detail="no amendment notes in consolidated text")
