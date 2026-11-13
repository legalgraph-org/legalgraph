"""Does the amendment the graph recorded still match what the portal shows?"""

import re
from datetime import date, datetime

from rdflib import Graph

from legalgraph.amendments.graph import graph_checks
from legalgraph.amendments.model import GraphCheck, LiveAmendment, Result, parse_date
from legalgraph.amendments.registry import exempt_acts, fetch_live, live_checks, registry

_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"


def citation_key(citation: str) -> frozenset[str]:
    """The comparable tokens of an amendment citation, portal-format independent.

    Every date becomes ISO, every instrument number its canonical form; two citations that name
    the same act in different house styles produce the same token set.
    """
    c = citation.lower()
    c = re.sub(r"3(\d{4})[lrd](\d{3,6})", lambda m: f"{m.group(1)}/{int(m.group(2))}", c)  # CELEX -> year/nr
    out: set[str] = set()
    for pat, fmt in (
        (r"art\. ?(\d+)(?:\s*abs\.? ?(\d+))?", lambda m: "art" + "".join(g or "0" for g in m.groups())),
        (r"v\. ?(\d{1,2}\.\d{1,2}\.\d{4})", lambda m: "v:" + (parse_date(m.group(1)) or date.min).isoformat()),
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
        (r"(\d{1,2}[./]\d{1,2}[./]\d{4})", lambda m: "d" + (parse_date(m.group(1)) or date.min).isoformat()),
        (
            rf"({_MONTHS}) (\d{{1,2}}), (\d{{4}})",
            lambda m: "d" + datetime.strptime(m.group(0), "%B %d, %Y").date().isoformat(),
        ),
        (r"№ ?(\d+/\d{4})", lambda m: "nn" + m.group(1)),
    ):
        for m in re.finditer(pat, c):
            out.add(fmt(m))
    return frozenset(out)


def year_number(citation: str) -> tuple[int, int] | None:
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


def failed(act: str, message: str) -> Result:
    return Result(act, ok=False, skipped=False, message=message)


def passed(act: str, message: str) -> Result:
    return Result(act, ok=True, skipped=False, message=message)


def compare_repeal(act: str, graph: GraphCheck, live: LiveAmendment) -> Result:
    if "repeal" in graph.comment.lower():
        return passed(act, f"repealed ({live.detail})")
    return failed(act, f"portal says {live.detail}; graph does not mark it repealed")


def compare_instrument(act: str, graph: GraphCheck, live: LiveAmendment) -> Result:
    """By instrument number, where the portal gives no precise date (legislation.gov.uk, riksdagen)."""
    recorded = year_number(graph.citation or "")
    if recorded is None and graph.amendment_date:
        recorded = (graph.amendment_date.year, 0)
    if recorded is None:
        return failed(act, f"portal cites {live.citation} but graph has no comparable citation")
    if (live.year or 0, live.number or 0) > recorded:
        return failed(act, f"STALE: portal cites newer instrument {live.citation} than graph's {graph.citation!r}")
    return passed(act, f"{live.citation} (portal: {live.detail})")


def same_citation(graph: GraphCheck, live: LiveAmendment) -> bool:
    if not (graph.citation and live.citation):
        return True
    recorded, shown = citation_key(graph.citation), citation_key(live.citation)
    return not (recorded and shown) or recorded == shown or recorded < shown or shown < recorded


def compare_undated(act: str, graph: GraphCheck, live: LiveAmendment) -> Result:
    """The portal shows no amendment: neither may the graph."""
    if graph.amendment_date is None and graph.citation is None:
        return passed(act, f"no amendment on either side ({live.detail})")
    return failed(act, f"graph records {graph.citation!r} but portal found none ({live.detail})")


def compare_dates(act: str, graph: GraphCheck, live: LiveAmendment) -> Result:
    if live.date is None:
        return compare_undated(act, graph, live)
    recorded = [d for d in (graph.amendment_date, graph.in_force) if d]
    if not recorded:
        return failed(act, f"portal shows {live.citation} ({live.date}) but graph records no amendment date")
    latest = max(recorded)
    if live.date > latest:
        return failed(
            act, f"STALE: portal shows {live.citation} ({live.date}) newer than graph's {graph.citation!r} ({latest})"
        )
    if live.date not in recorded:
        return failed(
            act,
            f"graph's {graph.citation!r} ({latest}) is newer than the portal's "
            f"{live.citation} ({live.date}) — wrong date?",
        )
    if not same_citation(graph, live):
        return failed(act, f"citation mismatch: graph {graph.citation!r} vs portal {live.citation!r}")
    return passed(act, f"{graph.citation or '(none)'} ({latest}) matches portal")


def compare(act: str, graph: GraphCheck | None, live: LiveAmendment | None) -> Result:
    """Does the graph's recorded amendment still match what the portal shows?"""
    if live is None:
        reason = exempt_acts(registry()).get(act, "not covered (see coverage.yaml)")
        return Result(act, ok=True, skipped=True, message=f"skip: {reason}")
    if graph is None:
        return failed(act, "no lgo:AmendmentCheck in the graph")
    if live.repealed_by:
        return compare_repeal(act, graph, live)
    if live.date is None and live.year:
        return compare_instrument(act, graph, live)
    return compare_dates(act, graph, live)


def run(ids: list[str] | None = None, data_graph: Graph | None = None) -> list[Result]:
    """Check the given acts (default: every act with a live checker). ids are act ids or
    jurisdiction codes (DE, EU, GB ...)."""
    covered = live_checks(registry())
    acts = sorted(covered) if not ids else sorted(a for a in covered for i in ids if a == i or a.startswith(f"{i}-"))
    checks = graph_checks(data_graph if data_graph is not None else Graph())
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
