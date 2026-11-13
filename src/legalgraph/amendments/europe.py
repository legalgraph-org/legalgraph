"""National portals in Europe: what each shows as the act's latest amendment or version."""

import json
import re
import urllib.parse

from legalgraph.amendments.model import LiveAmendment, get, page_text, parse_date


def check_gesetze(slug: str) -> LiveAmendment:
    """The act's standangabe, from the full-text page (the TOC page carries no Stand line)."""
    toc = get(f"https://www.gesetze-im-internet.de/{slug}/")
    bjnr = re.search(rb'href="(BJNR[A-Z0-9]+\.html)"', toc)
    if not bjnr:
        return LiveAmendment(detail="(no BJNR link on the TOC page)")
    page = get(f"https://www.gesetze-im-internet.de/{slug}/{bjnr.group(1).decode()}")
    text = page_text(page)
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
        date=parse_date(dates[-1]) if dates else None,
        detail=f"geändert durch {citation}",
    )


def check_ris(gesetzesnummer: str) -> LiveAmendment:
    text = page_text(
        get(f"https://www.ris.bka.gv.at/GeltendeFassung.wxe?Abfrage=Bundesnormen&Gesetzesnummer={gesetzesnummer}")
    )
    fassung = re.search(r"Fassung vom ([\d.]+)", text)
    amenders = re.findall(r"BGBl\. (?:I|II)? ?Nr\. (\d+)/(\d{4})", text)
    live = LiveAmendment(detail=fassung.group(0) if fassung else "(no Fassung found)")
    if amenders:
        nr, yr = max(((int(n), int(y)) for n, y in amenders), key=lambda t: (t[1], t[0]))
        live.citation = f"BGBl. Nr. {nr}/{yr}"
        live.year, live.number = yr, nr
    return live


def check_fedlex(eli: str) -> LiveAmendment:
    sparql = (
        "SELECT ?d WHERE { ?v <http://data.legilux.public.lu/resource/ontology/jolux#isMemberOf> "
        f"<https://fedlex.data.admin.ch/eli/{eli}> ; "
        "<http://data.legilux.public.lu/resource/ontology/jolux#dateApplicability> ?d . } "
        "ORDER BY DESC(?d) LIMIT 1"
    )
    url = "https://fedlex.data.admin.ch/sparqlendpoint?" + urllib.parse.urlencode({"query": sparql})
    body = get(url, {"Accept": "text/csv"}).decode("utf-8", "replace")
    rows = [r.strip().strip('"') for r in body.splitlines()[1:] if r.strip()]
    if rows:
        return LiveAmendment(
            citation=f"version of {rows[0]}", date=parse_date(rows[0]), detail=f"fedlex version {rows[0]}"
        )
    return LiveAmendment(detail="no versions in fedlex SPARQL")


def check_normattiva(urn: str) -> LiveAmendment:
    text = page_text(get(f"https://www.normattiva.it/uri-res/N2Ls?urn:{urn}"))
    m = re.search(r"Ultimo aggiornamento all'?atto pubblicato il ([\d/]+)", text)
    if m:
        return LiveAmendment(citation=f"aggiornamento {m.group(1)}", date=parse_date(m.group(1)), detail=m.group(0))
    return LiveAmendment(detail="no 'ultimo aggiornamento' found")


def check_boe(boe_id: str) -> LiveAmendment:
    text = page_text(get(f"https://www.boe.es/buscar/act.php?id={boe_id}"))
    m = re.search(r"Última actualización,? publicada el ([\d/]+)", text)
    if m:
        return LiveAmendment(citation=f"actualización {m.group(1)}", date=parse_date(m.group(1)), detail=m.group(0))
    return LiveAmendment(detail="no 'última actualización' found")


def check_pgdl(nid: str) -> LiveAmendment:
    page = get(f"https://www.pgdlisboa.pt/leis/lei_mostra_articulado.php?nid={nid}&tabela=leis")
    text = page_text(page)
    m = re.search(r"a mais recente \(([^)]+ de [\d/]+)\)", text)
    if m:
        d = re.search(r"de (\d{2}/\d{2})", m.group(1))
        y = re.search(r"(\d{4})", m.group(1))
        when = None
        if d and y:
            dd, mm = d.group(1).split("/")
            when = parse_date(f"{y.group(1)}-{mm}-{dd}")
        return LiveAmendment(citation=m.group(1), date=when, detail=f"última versão: {m.group(1)}")
    return LiveAmendment(detail="no 'mais recente' version found")


def check_legislation_mt(eli: str) -> LiveAmendment:
    page = get(f"https://legislation.mt/eli/{eli}/eng")
    for blob in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', page.decode("utf-8", "replace"), re.S
    ):
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue
        when = parse_date(str(data.get("datePublished", "")))
        if when:
            return LiveAmendment(citation=f"version {when.isoformat()}", date=when, detail=f"datePublished {when}")
    m = re.search(r"(\d{4}-\d{2}-\d{2}).{0,40}legislationIdentifier", page.decode("utf-8", "replace"))
    if m:
        return LiveAmendment(citation=f"version {m.group(1)}", date=parse_date(m.group(1)), detail=m.group(0))
    return LiveAmendment(detail="no version date found")


def check_lovdata(act: str) -> LiveAmendment:
    text = page_text(get(f"https://lovdata.no/dokument/NL/lov/{act}"))
    m = re.search(r"Sist endret (LOV-\d{4}-\d{2}-\d{2})-(\d+)(?: fra ([\d.]+))?", text)
    if m:
        return LiveAmendment(
            citation=f"{m.group(1)}-{m.group(2)}",
            date=parse_date(m.group(1)[4:]),
            detail=m.group(0),
        )
    return LiveAmendment(detail="no 'sist endret' found")


def check_riksdagen(act: str) -> LiveAmendment:
    page = get(f"https://www.riksdagen.se/sv/dokument-och-lagar/dokument/svensk-forfattningssamling/{act}")
    text = page_text(page)
    m = re.search(r"Ändrad\s*:?\s*t\.o\.m\. (SFS \d{4}:\d+)", text)
    if m:
        y, n = m.group(1).replace("SFS ", "").split(":")
        return LiveAmendment(citation=m.group(1), year=int(y), number=int(n), detail=m.group(0))
    return LiveAmendment(detail="no 'Ändrad t.o.m.' found")


def check_wetten(bwbr: str) -> LiveAmendment:
    page = get(f"https://wetten.overheid.nl/{bwbr}/").decode("utf-8", "replace")
    dates = [d for d in (parse_date(m) for m in re.findall(r'data-inwerking="(\d{2}-\d{2}-\d{4})"', page)) if d]
    if dates:
        latest = max(dates)
        return LiveAmendment(
            citation=f"geldig vanaf {latest:%d-%m-%Y}", date=latest, detail=f"in force version from {latest}"
        )
    return LiveAmendment(detail="no inwerking date found")


def check_isap(eli_addr: str) -> LiveAmendment:
    """The act's status and metadata change date from the official ELI API."""
    data = json.loads(get(f"https://api.sejm.gov.pl/eli/acts/{eli_addr}"))
    return LiveAmendment(
        citation=data.get("displayAddress", ""),
        date=parse_date((data.get("changeDate") or "")[:10]),
        detail=f"{data.get('status', '?')}, changed {data.get('changeDate', '?')}",
    )
