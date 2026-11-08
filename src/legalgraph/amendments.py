"""Live amendment checks: does the official portal still show the amendment the graph recorded?

Each registered checker fetches the act's official page, extracts the latest amendment the portal
knows, and `compare()` contrasts it with the `lgo:AmendmentCheck` data under
`data/amendment-checks/`. Portals that cannot be read programmatically (JavaScript-only, blocked,
no version metadata) have no checker: their acts are skipped rather than faked.

Usage:
    legalgraph checks amendments                    # every registered act
    legalgraph checks amendments EU DE              # a jurisdiction group
    legalgraph checks amendments EU-2016-679 DE-UWG # single acts
"""

from __future__ import annotations

import io
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup
from rdflib import Graph

from legalgraph.sources import download

LGO = "https://legalgraph.org/ontology#"
LG = "https://legalgraph.org/id/"

CELLAR = "https://publications.europa.eu/resource/celex/{}"
CELLAR_NOTICE = {"Accept": "application/xml;notice=object"}
CELLAR_TREE = {"Accept": "application/xml;notice=tree"}

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


def _get(url: str, headers: dict[str, str] | None = None) -> bytes:
    time.sleep(PAUSE)
    try:
        return download(url, headers)
    except Exception as error:
        # urllib's certificate store misses some national portals (ris.bka.gv.at, pgdlisboa.pt,
        # riksdagen.se); curl uses the system keychain where urllib does not.
        if "CERTIFICATE_VERIFY_FAILED" not in str(error):
            raise
        import subprocess

        return subprocess.run(
            ["curl", "-sfL", "-A", "legalgraph (+https://legalgraph.org)", "-m", "60", url],
            capture_output=True,
            check=True,
        ).stdout


def _text(page: bytes) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(page, "html.parser").get_text(" "))


def _d(s: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    return None


# --- gesetze-im-internet.de ---------------------------------------------------


def check_gesetze(slug: str) -> LiveAmendment:
    """The act's standangabe, from the full-text page (the TOC page carries no Stand line)."""
    toc = _get(f"https://www.gesetze-im-internet.de/{slug}/")
    bjnr = re.search(rb'href="(BJNR[A-Z0-9]+\.html)"', toc)
    if not bjnr:
        return LiveAmendment(detail="(no BJNR link on the TOC page)")
    page = _get(f"https://www.gesetze-im-internet.de/{slug}/{bjnr.group(1).decode()}")
    text = _text(page)
    # Standangabe layout varies ("Stand:", "Hinweis:", table cells) — the last
    # "geändert durch" on the page is the act's latest amendment wherever the portal puts it.
    changes = re.findall(
        r"(?:geändert|Änderung|Neugefasst)\s+durch\s+([^;]{1,120}?v\.\s*[\d.]+\s*I\s*Nr\.\s*\d+)", text, re.I
    )
    if not changes:
        return LiveAmendment(detail="(no amendment note on the act page)")
    # The capture can include a running-on Bekanntmachung ("... I 202 Zuletzt geändert durch
    # Art. ...") — the amendment is the last citation of the form "v. DD.MM.YYYY I Nr. N".
    inner = re.findall(r"(Art\.[^;]*?v\.\s*[\d.]+\s*I\s*Nr\.\s*\d+|Bek\.\s*v\.\s*[\d.]+\s*I\s*Nr\.\s*\d+)", changes[-1])
    citation = inner[-1] if inner else changes[-1]
    dates = re.findall(r"v\.\s*([\d.]+)\s*I\s*Nr\.", citation)
    return LiveAmendment(
        citation=citation,
        date=_d(dates[-1]) if dates else None,
        detail=f"geändert durch {citation}",
    )


# --- EUR-Lex / Cellar ---------------------------------------------------------

_eu_date_cache: dict[str, date | None] = {}


def _cellar_date(celex: str) -> date | None:
    """The WORK_DATE_DOCUMENT of a CELEX work (its adoption/signature date)."""
    if celex in _eu_date_cache:
        return _eu_date_cache[celex]
    try:
        root = ET.parse(io.BytesIO(_get(CELLAR.format(celex), CELLAR_NOTICE))).getroot()
        for work in root.findall(".//WORK"):
            cid = work.find("RESOURCE_LEGAL_ID_CELEX/VALUE")
            if cid is not None and cid.text == celex:
                v = work.find("WORK_DATE_DOCUMENT/VALUE")
                _eu_date_cache[celex] = _d(v.text) if v is not None and v.text else None
                break
        else:
            _eu_date_cache[celex] = None
    except Exception:
        _eu_date_cache[celex] = None
    return _eu_date_cache[celex]


def check_cellar(celex: str) -> LiveAmendment:
    tree = _get(CELLAR.format(celex), CELLAR_TREE).decode("utf-8", "replace")

    def link_ids(tag: str) -> list[str]:
        return [
            inner.group(1)
            for outer in re.finditer(rf'<{tag} type="link">(.*?)</{tag}>', tree, re.S)
            for inner in re.finditer(r"<IDENTIFIER>(3[0-9A-Z()]{8,14})</IDENTIFIER>", outer.group(1))
        ]

    repeal = link_ids("RESOURCE_LEGAL_REPEALED_BY_RESOURCE_LEGAL")
    if repeal:
        return LiveAmendment(detail=f"repealed by {repeal[-1]}", repealed_by=repeal[-1])
    best: tuple[date | None, str | None] = (None, None)
    for amender in link_ids("RESOURCE_LEGAL_AMENDED_BY_RESOURCE_LEGAL"):
        d = _cellar_date(amender)
        if d is not None and (best[0] is None or d > best[0]):
            best = (d, amender)
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


# --- legislation.gov.uk -------------------------------------------------------


def check_legislation_gov(path: str) -> LiveAmendment:
    """The latest amending instrument on the act page: anything cited as "by S.I. YYYY/NNN" or
    "by YYYY c. NN", in the outstanding-changes list or in the applied annotations."""
    page = _get(f"https://www.legislation.gov.uk/{path}")
    text = _text(page)
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


# --- RIS (AT) -----------------------------------------------------------------


def check_ris(gesetzesnummer: str) -> LiveAmendment:
    text = _text(
        _get(f"https://www.ris.bka.gv.at/GeltendeFassung.wxe?Abfrage=Bundesnormen&Gesetzesnummer={gesetzesnummer}")
    )
    fassung = re.search(r"Fassung vom ([\d.]+)", text)
    amenders = re.findall(r"BGBl\. (?:I|II)? ?Nr\. (\d+)/(\d{4})", text)
    live = LiveAmendment(detail=fassung.group(0) if fassung else "(no Fassung found)")
    if amenders:
        nr, yr = max(((int(n), int(y)) for n, y in amenders), key=lambda t: (t[1], t[0]))
        live.citation = f"BGBl. Nr. {nr}/{yr}"
        live.year, live.number = yr, nr
    return live


# --- laws-lois.justice.gc.ca ---------------------------------------------------


def check_laws_lois(slug: str) -> LiveAmendment:
    text = _text(_get(f"https://laws-lois.justice.gc.ca/eng/acts/{slug}/"))
    m = re.search(r"last amended on (\d{4}-\d{2}-\d{2})", text, re.I)
    if m:
        return LiveAmendment(citation=f"last amended on {m.group(1)}", date=_d(m.group(1)), detail=m.group(0))
    return LiveAmendment(detail="no 'last amended' statement found")


# --- fedlex (CH) ---------------------------------------------------------------


def check_fedlex(eli: str) -> LiveAmendment:
    sparql = (
        "SELECT ?d WHERE { ?v <http://data.legilux.public.lu/resource/ontology/jolux#isMemberOf> "
        f"<https://fedlex.data.admin.ch/eli/{eli}> ; "
        "<http://data.legilux.public.lu/resource/ontology/jolux#dateApplicability> ?d . } "
        "ORDER BY DESC(?d) LIMIT 1"
    )
    url = "https://fedlex.data.admin.ch/sparqlendpoint?" + urllib.parse.urlencode({"query": sparql})
    body = _get(url, {"Accept": "text/csv"}).decode("utf-8", "replace")
    rows = [r.strip().strip('"') for r in body.splitlines()[1:] if r.strip()]
    if rows:
        return LiveAmendment(citation=f"version of {rows[0]}", date=_d(rows[0]), detail=f"fedlex version {rows[0]}")
    return LiveAmendment(detail="no versions in fedlex SPARQL")


# --- normattiva (IT) ------------------------------------------------------------


def check_normattiva(urn: str) -> LiveAmendment:
    text = _text(_get(f"https://www.normattiva.it/uri-res/N2Ls?urn:{urn}"))
    m = re.search(r"Ultimo aggiornamento all'?atto pubblicato il ([\d/]+)", text)
    if m:
        return LiveAmendment(citation=f"aggiornamento {m.group(1)}", date=_d(m.group(1)), detail=m.group(0))
    return LiveAmendment(detail="no 'ultimo aggiornamento' found")


# --- BOE (ES) -------------------------------------------------------------------


def check_boe(boe_id: str) -> LiveAmendment:
    text = _text(_get(f"https://www.boe.es/buscar/act.php?id={boe_id}"))
    m = re.search(r"Última actualización,? publicada el ([\d/]+)", text)
    if m:
        return LiveAmendment(citation=f"actualización {m.group(1)}", date=_d(m.group(1)), detail=m.group(0))
    return LiveAmendment(detail="no 'última actualización' found")


# --- PGDL (PT) -------------------------------------------------------------------


def check_pgdl(nid: str) -> LiveAmendment:
    page = _get(f"https://www.pgdlisboa.pt/leis/lei_mostra_articulado.php?nid={nid}&tabela=leis")
    text = _text(page)
    m = re.search(r"a mais recente \(([^)]+ de [\d/]+)\)", text)
    if m:
        d = re.search(r"de (\d{2}/\d{2})", m.group(1))
        y = re.search(r"(\d{4})", m.group(1))
        when = None
        if d and y:
            dd, mm = d.group(1).split("/")
            when = _d(f"{y.group(1)}-{mm}-{dd}")
        return LiveAmendment(citation=m.group(1), date=when, detail=f"última versão: {m.group(1)}")
    return LiveAmendment(detail="no 'mais recente' version found")


# --- legislation.mt ---------------------------------------------------------------


def check_legislation_mt(eli: str) -> LiveAmendment:
    page = _get(f"https://legislation.mt/eli/{eli}/eng")
    for blob in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', page.decode("utf-8", "replace"), re.S
    ):
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        when = _d(str(data.get("datePublished", "")))
        if when:
            return LiveAmendment(citation=f"version {when.isoformat()}", date=when, detail=f"datePublished {when}")
    m = re.search(r"(\d{4}-\d{2}-\d{2}).{0,40}legislationIdentifier", page.decode("utf-8", "replace"))
    if m:
        return LiveAmendment(citation=f"version {m.group(1)}", date=_d(m.group(1)), detail=m.group(0))
    return LiveAmendment(detail="no version date found")


# --- lovdata (NO) ------------------------------------------------------------------


def check_lovdata(act: str) -> LiveAmendment:
    text = _text(_get(f"https://lovdata.no/dokument/NL/lov/{act}"))
    m = re.search(r"Sist endret (LOV-\d{4}-\d{2}-\d{2})-(\d+)(?: fra ([\d.]+))?", text)
    if m:
        return LiveAmendment(
            citation=f"{m.group(1)}-{m.group(2)}",
            date=_d(m.group(1)[4:]),
            detail=m.group(0),
        )
    return LiveAmendment(detail="no 'sist endret' found")


# --- riksdagen (SE) ------------------------------------------------------------------


def check_riksdagen(act: str) -> LiveAmendment:
    page = _get(f"https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/{act}")
    text = _text(page)
    m = re.search(r"Ändrad\s*:?\s*t\.o\.m\. (SFS \d{4}:\d+)", text)
    if m:
        y, n = m.group(1).replace("SFS ", "").split(":")
        return LiveAmendment(citation=m.group(1), year=int(y), number=int(n), detail=m.group(0))
    return LiveAmendment(detail="no 'Ändrad t.o.m.' found")


# --- wetten.overheid.nl (NL) -----------------------------------------------------------


def check_wetten(bwbr: str) -> LiveAmendment:
    page = _get(f"https://wetten.overheid.nl/{bwbr}/").decode("utf-8", "replace")
    dates = [d for d in (_d(m) for m in re.findall(r'data-inwerking="(\d{2}-\d{2}-\d{4})"', page)) if d]
    if dates:
        latest = max(dates)
        return LiveAmendment(
            citation=f"geldig vanaf {latest:%d-%m-%Y}", date=latest, detail=f"in force version from {latest}"
        )
    return LiveAmendment(detail="no inwerking date found")


# --- eCFR (US) --------------------------------------------------------------------------


def check_ecfr(title: str, part: str, section: str) -> LiveAmendment:
    url = f"https://www.ecfr.gov/api/versioner/v1/versions/title-{title}.json?part={part}&section={section}"
    data = json.loads(_get(url))
    versions = [v for v in data.get("content_versions", []) if v.get("substantive")]
    if versions:
        latest = max(versions, key=lambda v: v["amendment_date"])
        return LiveAmendment(
            citation=f"version {latest['amendment_date']}",
            date=_d(latest["amendment_date"]),
            detail=f"eCFR {latest['identifier']} version {latest['amendment_date']}",
        )
    return LiveAmendment(detail="no versions in eCFR API")


# --- govinfo USCODE (US) -------------------------------------------------------------------


def check_uscode(pkg: str, htm: str) -> LiveAmendment:
    page = _get(f"https://www.govinfo.gov/content/pkg/{pkg}/html/{htm}.htm")
    text = _text(page)
    m = re.search(r"Amendments\s+(.*?)(?:Statutory Notes|Cross References|Miscellaneous)", text)
    if m:
        pls = re.findall(r"Pub\. L\. [\d–-]+", m.group(1))
        return LiveAmendment(citation=pls[-1] if pls else "amendment note present", detail=m.group(1)[:200])
    return LiveAmendment(detail="no Amendments note")


# --- CPPA (US-CA) -----------------------------------------------------------------------------


def check_cppa(url: str) -> LiveAmendment:
    text = _text(_get(url))
    m = re.search(r"CCPA Regulations \(Effective ([A-Z][a-z]+ \d{1,2}, \d{4})\)", text)
    if not m:
        m = re.search(r"CCPA Regulations[^)]*Effective ([A-Z][a-z]+ \d{1,2}, \d{4})", text)
    if m:
        when = datetime.strptime(m.group(1), "%B %d, %Y").date()
        return LiveAmendment(citation=f"effective {m.group(1)}", date=when, detail=m.group(0))
    return LiveAmendment(detail="no effective date found on CPPA page")


# --- mevzuat (TR) -------------------------------------------------------------------------------


def check_mevzuat(act: str) -> LiveAmendment:
    from pypdf import PdfReader

    pdf = _get(f"https://www.mevzuat.gov.tr/mevzuatmetin/{act}.pdf")
    text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)
    changes = re.findall(r"(?:Değişik|Ek|Mülga|İptal|İhdas):\s*(\d{1,2}/\d{1,2}/\d{4})-(\d+)", text)
    if changes:
        latest = max(((_d(c[0]), c[1]) for c in changes if _d(c[0])), key=lambda t: t[0])
        return LiveAmendment(citation=f"Kanun {latest[1]}", date=latest[0], detail=f"Değişik: {latest[0]}-{latest[1]}")
    return LiveAmendment(detail="no amendment notes in consolidated text")


# --- The registry: which acts the live check covers, and why not ----------------------------------
#
# The committed registry is data/amendment-checks/coverage.yaml — one line per lgo:LegalAct:
# covered acts carry `kind` (a checker below) and `arg` (the portal identifier), exempt acts
# carry `exempt` with the reason. Every act in the graph must be registered (tested).


def checker_kinds() -> dict:
    """kind -> fetcher function, keyed as coverage.yaml uses them."""
    return {
        "gesetze": check_gesetze,
        "cellar": check_cellar,
        "legislation": check_legislation_gov,
        "ris": check_ris,
        "laws_lois": check_laws_lois,
        "fedlex": check_fedlex,
        "normattiva": check_normattiva,
        "boe": check_boe,
        "pgdl": check_pgdl,
        "legislation_mt": check_legislation_mt,
        "lovdata": check_lovdata,
        "riksdagen": check_riksdagen,
        "wetten": check_wetten,
        "ecfr": lambda arg: check_ecfr(*arg.split(":")),
        "uscode": lambda arg: check_uscode(*arg.split(":")),
        "cppa": check_cppa,
        "mevzuat": check_mevzuat,
    }


def load_registry(path: Path | None = None) -> dict[str, dict]:
    """The committed coverage registry: act id -> {kind, arg} or {exempt}."""
    import yaml

    if path is None:
        from legalgraph.load import DEFAULT_DATA_DIR

        path = DEFAULT_DATA_DIR / "amendment-checks" / "coverage.yaml"
    return yaml.safe_load(path.read_text())


def live_checks(registry: dict[str, dict]) -> dict[str, tuple[str, str]]:
    """act id -> (arg, kind) for every covered entry."""
    return {act: (e["arg"], e["kind"]) for act, e in registry.items() if "kind" in e}


def exempt_acts(registry: dict[str, dict]) -> dict[str, str]:
    """act id -> exemption reason."""
    return {act: e["exempt"] for act, e in registry.items() if "exempt" in e}


_REGISTRY: dict[str, dict] | None = None


def registry(path: Path | None = None) -> dict[str, dict]:
    """The committed coverage registry, loaded once."""
    global _REGISTRY
    if path is not None:
        return load_registry(path)
    if _REGISTRY is None:
        _REGISTRY = load_registry()
    return _REGISTRY


def fetch_live(act: str) -> LiveAmendment | None:
    """The latest amendment the official portal shows for `act`, or None when no checker exists."""
    entry = live_checks(registry()).get(act)
    if entry is None:
        return None
    arg, kind = entry
    return checker_kinds()[kind](arg)


def graph_checks(graph: Graph) -> dict[str, GraphCheck]:
    """All lgo:AmendmentCheck data in the graph, keyed by act id."""
    out: dict[str, GraphCheck] = {}
    for s in graph.subjects():
        sid = str(s)
        if not sid.startswith(LG) or not sid.endswith("-amendment-check"):
            continue
        act = sid[len(LG) :][: -len("-amendment-check")]
        gc = GraphCheck()
        for p, o in graph.predicate_objects(s):
            name = str(p)[len(LGO) :]
            if name == "checkedOn":
                gc.checked_on = _d(str(o))
            elif name == "sourceUrl":
                gc.source_url = str(o)
            elif name == "lastKnownAmendment":
                gc.citation = str(o)
            elif name == "lastKnownAmendmentDate":
                gc.amendment_date = _d(str(o))
            elif name == "lastKnownAmendmentInForce":
                gc.in_force = _d(str(o))
            elif name == "sourceIsCurrent":
                gc.current = str(o).lower() in ("true", "1")
            elif str(p).endswith("comment"):
                gc.comment = str(o)
        out[act] = gc
    return out


_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"


def _key(citation: str) -> frozenset[str]:
    """The comparable tokens of an amendment citation, portal-format independent.

    Every date becomes ISO, every instrument number its canonical form; two citations that name
    the same act in different house styles produce the same token set.
    """
    c = citation.lower()
    c = re.sub(r"3(\d{4})[lrd](\d{3,6})", lambda m: f"{m.group(1)}/{int(m.group(2))}", c)  # CELEX -> year/nr
    out: set[str] = set()
    for pat, fmt in (
        (r"art\. ?(\d+)(?:\s*abs\.? ?(\d+))?", lambda m: "art" + "".join(g or "0" for g in m.groups())),
        (r"v\. ?(\d{1,2}\.\d{1,2}\.\d{4})", lambda m: "v:" + (_d(m.group(1)) or date.min).isoformat()),
        (r"nr\.? ?(\d+)", lambda m: "nr" + m.group(1)),
        (r"(\d{4})/(\d+)", lambda m: f"{m.group(1)}/{m.group(2)}"),
        (r"nr\.? ?(\d+/\d{4})", lambda m: "nr" + m.group(1)),
        (r"(\d{4}) c\. ?(\d+)", lambda m: f"{m.group(1)}c{m.group(2)}"),
        (r"ch\.? ?(\d+)", lambda m: "ch" + m.group(1)),
        (r"kanun (\d+)", lambda m: "kanun" + m.group(1)),
        (r"lei n\.º? ?([0-9a-z/º-]+)", lambda m: "lei" + m.group(1)),
        (r"lov-(\d{4}-\d{2}-\d{2}-\d+)", lambda m: "lov" + m.group(1)),
        (r"sfs ?(\d{4}:\d+)", lambda m: "sfs" + m.group(1)),
        (r"№ ?([0-9]+-[ivx]+)", lambda m: "zakon" + m.group(1)),
        (r"(\d{4}-\d{2}-\d{2})", lambda m: "d" + m.group(1)),
        (r"(\d{1,2}[./]\d{1,2}[./]\d{4})", lambda m: "d" + (_d(m.group(1)) or date.min).isoformat()),
        (
            rf"({_MONTHS}) (\d{{1,2}}), (\d{{4}})",
            lambda m: "d" + datetime.strptime(m.group(0), "%B %d, %Y").date().isoformat(),
        ),
        (r"№ ?(\d+/\d{4})", lambda m: "nn" + m.group(1)),
    ):
        for m in re.finditer(pat, c):
            out.add(fmt(m))
    return frozenset(out)


def _year_number(citation: str) -> tuple[int, int] | None:
    """(year, number) of an instrument citation, across portal formats."""
    for pat, swapped in (
        (r"(\d{4})/(\d+)", False),  # S.I. 2026/1015
        (r"Nr\. ?(\d+)/(\d{4})", True),  # BGBl. I Nr. 94/2025
        (r"(\d{4}) c\. (\d+)", False),  # 2026 c. 18
        (r"(\d{4}), Ch\. (\d+)", False),  # Stats. 2025, Ch. 67
        (r"(\d{4}):(\d+)", False),  # SFS 2025:989
    ):
        m = re.search(pat, citation)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            return (b, a) if swapped else (a, b)
    m = re.search(r"(\d{4})-([IVX]+)", citation)
    return (int(m.group(1)), 0) if m else None


def compare(act: str, graph: GraphCheck | None, live: LiveAmendment | None) -> Result:
    """Does the graph's recorded amendment still match what the portal shows?"""
    if live is None:
        reason = exempt_acts(registry()).get(act, "not covered (see coverage.yaml)")
        return Result(act, ok=True, skipped=True, message=f"skip: {reason}")
    if graph is None:
        return Result(act, ok=False, skipped=False, message="no lgo:AmendmentCheck in the graph")
    if live.repealed_by:
        if "repeal" in graph.comment.lower():
            return Result(act, ok=True, skipped=False, message=f"repealed ({live.detail})")
        return Result(
            act, ok=False, skipped=False, message=f"portal says {live.detail}; graph does not mark it repealed"
        )
    # Instrument-number comparison where the portal gives no precise date (legislation.gov.uk, riksdagen)
    if live.date is None and live.year:
        gyn = _year_number(graph.citation or "")
        gyn = gyn or (graph.amendment_date.year, 0) if graph.amendment_date else gyn
        if gyn is None:
            return Result(
                act,
                ok=False,
                skipped=False,
                message=f"portal cites {live.citation} but graph has no comparable citation",
            )
        if (live.year, live.number or 0) > gyn:
            return Result(
                act,
                ok=False,
                skipped=False,
                message=f"STALE: portal cites newer instrument {live.citation} than graph's {graph.citation!r}",
            )
        return Result(act, ok=True, skipped=False, message=f"{live.citation} (portal: {live.detail})")
    # Date comparison everywhere else
    if live.date is None:
        if graph.amendment_date is None and graph.citation is None:
            return Result(act, ok=True, skipped=False, message=f"no amendment on either side ({live.detail})")
        return Result(
            act,
            ok=False,
            skipped=False,
            message=f"graph records {graph.citation!r} but portal found none ({live.detail})",
        )
    gdates = [d for d in (graph.amendment_date, graph.in_force) if d]
    if not gdates:
        return Result(
            act,
            ok=False,
            skipped=False,
            message=f"portal shows {live.citation} ({live.date}) but graph records no amendment date",
        )
    gdate = max(gdates)
    if live.date > gdate:
        return Result(
            act,
            ok=False,
            skipped=False,
            message=(
                f"STALE: portal shows {live.citation} ({live.date}) newer than graph's {graph.citation!r} ({gdate})"
            ),
        )
    if live.date not in gdates:
        return Result(
            act,
            ok=False,
            skipped=False,
            message=(
                f"graph's {graph.citation!r} ({gdate}) is newer than the portal's "
                f"{live.citation} ({live.date}) — wrong date?"
            ),
        )
    if graph.citation and live.citation:
        gk, lk = _key(graph.citation), _key(live.citation)
        if gk and lk and not (gk == lk or gk < lk or lk < gk):
            return Result(
                act,
                ok=False,
                skipped=False,
                message=f"citation mismatch: graph {graph.citation!r} vs portal {live.citation!r}",
            )
    return Result(act, ok=True, skipped=False, message=f"{graph.citation or '(none)'} ({gdate}) matches portal")


def run(ids: list[str] | None = None, data_graph: Graph | None = None) -> list[Result]:
    """Check the given acts (default: every act with a live checker). ids are act ids or
    jurisdiction codes (DE, EU, GB ...)."""
    covered = live_checks(registry())
    acts = sorted(covered) if not ids else sorted(a for a in covered for i in ids if a == i or a.startswith(f"{i}-"))
    if data_graph is None:
        data_graph = Graph()
    checks = graph_checks(data_graph)
    results = []
    for act in acts:
        try:
            live = fetch_live(act)
        except Exception as error:
            # Inconclusive, not a graph failure — the portal may be down or rate-limiting.
            results.append(Result(act, ok=True, skipped=True, message=f"fetch failed: {error}"))
            continue
        results.append(compare(act, checks.get(act), live))
    return results
