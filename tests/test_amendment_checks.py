"""Amendment freshness: the graph's lgo:AmendmentCheck data against the live official portals.

The live tests need network. They run only under `-m live` (see pyproject addopts):

    uv run pytest -m live tests/test_amendment_checks.py
    uv run pytest -m live -k "EU-"                    # one group
    uv run legalgraph checks amendments EU DE         # same gate as a command
"""

from datetime import date

import pytest
from rdflib import Graph
from rdflib.namespace import RDF

from legalgraph import LG, LGO, amendments
from legalgraph.load import DEFAULT_DATA_DIR, DEFAULT_ONTOLOGY_DIR, Sources, load_all


@pytest.fixture(scope="session")
def data() -> Graph:
    graph, _, _, errors = load_all(Sources(data_dir=DEFAULT_DATA_DIR, ontology_dir=DEFAULT_ONTOLOGY_DIR))
    assert not errors
    return graph


@pytest.mark.live
@pytest.mark.parametrize("act", sorted(amendments.live_checks(amendments.registry())))
def test_recorded_amendment_matches_portal(act: str, data: Graph) -> None:
    """The official portal must not show a newer amendment than the graph recorded."""
    live = amendments.fetch_live(act)
    assert live is not None
    result = amendments.compare(act, amendments.graph_checks(data).get(act), live)
    assert result.ok, f"{act}: {result.message} — portal says: {live.detail}"


# --- coverage.yaml: every act is covered or consciously exempted ----------------


def test_every_act_is_registered_in_the_coverage_yaml(data: Graph) -> None:
    """Adding an lgo:LegalAct without a coverage.yaml entry fails here."""
    acts = {str(s).removeprefix(str(LG)) for s in data.subjects(RDF.type, LGO.LegalAct)}
    registered = amendments.registry()
    missing = sorted(acts - set(registered))
    assert not missing, f"no coverage.yaml entry for: {missing}"
    unknown_kinds = sorted(
        e["kind"] for e in registered.values() if "kind" in e and e["kind"] not in amendments.checker_kinds()
    )
    assert not unknown_kinds, f"unknown checker kind(s): {unknown_kinds}"
    malformed = sorted(
        act for act, e in registered.items() if not (("kind" in e and "arg" in e) ^ bool(e.get("exempt")))
    )
    assert not malformed, f"coverage.yaml entries need kind+arg or exempt: {malformed}"
    unknown_acts = sorted(set(registered) - acts)
    assert not unknown_acts, f"coverage.yaml registers non-acts: {unknown_acts}"


# --- compare(), offline ---------------------------------------------------------


def _g(citation=None, day=None, in_force=None, comment=""):
    return amendments.GraphCheck(
        citation=citation,
        amendment_date=day,
        in_force=in_force,
        comment=comment,
    )


def test_newer_amendment_on_the_portal_fails() -> None:
    r = amendments.compare(
        "X-1",
        _g("Regulation (EU) 2019/2161", date(2019, 11, 27)),
        amendments.LiveAmendment(citation="CELEX 32026L0001", date=date(2026, 3, 1)),
    )
    assert not r.ok and "STALE" in r.message


def test_older_amendment_on_the_portal_fails_too() -> None:
    r = amendments.compare(
        "X-1",
        _g("BGBl. I Nr. 94/2025", date(2025, 12, 30)),
        amendments.LiveAmendment(citation="BGBl. I Nr. 12/2020", date=date(2020, 1, 1)),
    )
    assert not r.ok


def test_same_amendment_passes_even_with_different_citation_style() -> None:
    r = amendments.compare(
        "X-1",
        _g("Directive (EU) 2019/2161", date(2019, 11, 27)),
        amendments.LiveAmendment(citation="CELEX 32019L2161", date=date(2019, 11, 27)),
    )
    assert r.ok


def test_no_amendment_on_either_side_passes() -> None:
    r = amendments.compare("X-1", _g(), amendments.LiveAmendment(detail="no AMENDED_BY"))
    assert r.ok


def test_an_amendment_the_graph_has_not_recorded_fails() -> None:
    r = amendments.compare("X-1", _g(), amendments.LiveAmendment(citation="S.I. 2026/42", date=date(2026, 5, 1)))
    assert not r.ok


def test_year_and_number_comparison_for_sis() -> None:
    r = amendments.compare(
        "X-1",
        _g("S.I. 2026/1015", date(2026, 1, 1)),
        amendments.LiveAmendment(citation="2026/82", year=2026, number=82),
    )
    assert r.ok
    r = amendments.compare(
        "X-1",
        _g("S.I. 2026/82", date(2026, 1, 1)),
        amendments.LiveAmendment(citation="2026/1015", year=2026, number=1015),
    )
    assert not r.ok


def test_a_repealed_act_is_ok_when_the_check_says_so() -> None:
    r = amendments.compare(
        "X-1",
        _g(comment="REPEALED by Regulation (EU) 2016/679"),
        amendments.LiveAmendment(repealed_by="32016R0679", detail="repealed by 32016R0679"),
    )
    assert r.ok
    r = amendments.compare("X-1", _g(), amendments.LiveAmendment(repealed_by="32016R0679"))
    assert not r.ok
