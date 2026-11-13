"""The case-law and enforcement layer: outcomes, penalty provisions, succession, licences and
link-only references."""

from pathlib import Path

import pytest
from rdflib import RDF, Graph, Literal

from legalgraph import LG, LGO, LGV
from legalgraph import sources as law_sources
from legalgraph.load import DEFAULT_DATA_DIR, DEFAULT_ONTOLOGY_DIR, Sources, load_all
from legalgraph.reasoning import load_rules
from legalgraph.validate import shacl_violations


@pytest.fixture(scope="module")
def graphs() -> tuple[Graph, Graph, Graph, Graph]:
    sources = Sources(data_dir=DEFAULT_DATA_DIR, ontology_dir=DEFAULT_ONTOLOGY_DIR)
    data, ontology, shapes, errors = load_all(sources)
    assert not errors
    return data, ontology, shapes, load_rules(sources)


def violations_after(graphs: tuple[Graph, Graph, Graph, Graph], turtle: str) -> list[str]:
    data, ontology, shapes, rules = graphs
    changed = Graph()
    for triple in data:
        changed.add(triple)
    for prefix, namespace in data.namespaces():
        changed.bind(prefix, namespace)
    changed.parse(data=turtle, format="turtle")
    return shacl_violations(changed, ontology, shapes, rules)


PREFIXES = """
@prefix lgo: <https://legalgraph.org/ontology#> .
@prefix lgv: <https://legalgraph.org/vocab/> .
@prefix lg:  <https://legalgraph.org/id/> .
@prefix eli: <http://data.europa.eu/eli/ontology#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
"""


def test_penalty_provisions_point_to_what_they_penalise(graphs: tuple[Graph, Graph, Graph, Graph]) -> None:
    data, *_ = graphs
    assert (LG["DE-TDDDG-s28-2"], LGO.penalises, LG["DE-TDDDG-s25-1"]) in data
    assert (LG["DE-DDG-s33-6-3"], LGO.penalises, LG["DE-DDG-s5-1"]) in data
    assert (LG["EU-2016-679-art83-5"], LGO.penalises, LG["EU-2016-679-art7-3"]) in data
    assert (LG["EU-2016-679-art83-4"], LGO.penalises, LG["EU-2016-679-art37-1"]) in data
    fine = str(data.value(LG["DE-TDDDG-s28-2-q1"], LGO.text))
    assert "dreihunderttausend Euro" in fine


def test_an_outcome_is_stated_in_a_quoted_point_of_its_decision(graphs: tuple[Graph, Graph, Graph, Graph]) -> None:
    data, *_ = graphs
    outcome = LG["DE-OLGK-2024-0119-outcome-1"]
    assert (LG["DE-OLGK-2024-0119"], LGO.hasOutcome, outcome) in data
    point = data.value(outcome, LGO.statedIn)
    assert "250.000,00 €" in str(data.value(LG[f"{point.removeprefix(str(LG))}-q1"], LGO.text))


def test_an_outcome_without_its_statement_is_caught(graphs: tuple[Graph, Graph, Graph, Graph]) -> None:
    errors = violations_after(
        graphs,
        PREFIXES
        + """
        lg:DE-OLGK-2024-0119 lgo:hasOutcome lg:test-outcome .
        lg:test-outcome a lgo:Outcome ; lgo:outcomeType lgv:Fine ; lgo:against "Example GmbH" ;
            lgo:amount 1000.0 ; lgo:reviewStatus lgv:Draft .
        """,
    )
    assert any("test-outcome" in e and "statedIn" in e for e in errors), errors
    assert any("test-outcome" in e and "currency" in e for e in errors), errors


def test_an_outcome_stated_in_another_decision_is_caught(graphs: tuple[Graph, Graph, Graph, Graph]) -> None:
    errors = violations_after(
        graphs,
        PREFIXES
        + """
        lg:DE-OLGK-2024-0119 lgo:hasOutcome lg:test-outcome .
        lg:test-outcome a lgo:Outcome ; lgo:outcomeType lgv:Injunction ; lgo:against "Example GmbH" ;
            lgo:statedIn lg:CJEU-C-673-17-ruling-1 ; lgo:reviewStatus lgv:Draft .
        """,
    )
    assert any("test-outcome" in e and "point of the decision" in e for e in errors), errors


def test_only_decisions_illustrate_rules(graphs: tuple[Graph, Graph, Graph, Graph]) -> None:
    errors = violations_after(graphs, PREFIXES + "lg:EU-2016-679 lgo:illustrates lg:EU-R-cookie-consent .")
    assert any("EU-2016-679" in e for e in errors), errors


def test_read_under_needs_the_continuing_provision(graphs: tuple[Graph, Graph, Graph, Graph]) -> None:
    data, *_ = graphs
    assert (LG["EU-2016-679-art4-7"], LGO.continues, LG["EU-1995-46-art2-d"]) in data
    errors = violations_after(graphs, PREFIXES + "lg:CJEU-C-673-17-ruling-1 lgo:readUnder lg:EU-1995-46-art2-d .")
    assert any("CJEU-C-673-17-ruling-1" in e and "continues" in e for e in errors), errors


def test_a_long_excerpt_of_someone_elses_work_is_caught(graphs: tuple[Graph, Graph, Graph, Graph]) -> None:
    long = "word " * 80
    errors = violations_after(
        graphs,
        PREFIXES
        + f"""
        lg:ref-test a lgo:ExternalReference ; dcterms:title "A news report" ; dcterms:publisher "A newspaper" ;
            lgo:sourceUrl "https://example.org/news"^^xsd:anyURI ; lgo:linkOnlyReason "third-party work" ;
            lgo:supports lg:DE-OLGK-2024-0119 ; lgo:excerpt "{long}"@en ; lgo:excerptLocator "para. 1" .
        """,
    )
    assert any("ref-test" in e and "300" in e for e in errors), errors


def test_link_only_list_becomes_external_references(tmp_path: Path) -> None:
    path = tmp_path / "link-only.yaml"
    path.write_text(
        """
- id: example-report
  title: "Regulator fines a shop"
  publisher: "Example News"
  url: "https://example.org/report"
  date: 2022-01-06
  why_link_only: "news report; third-party work"
  claim: "A shop was fined for its cookie banner"
  supports: [DE-OLGK-2024-0119]
  quote:
    text: "The regulator said refusing must be as easy as accepting."
    locator: "para. 2"
    language: en
"""
    )
    graph = Graph().parse(data=law_sources.extract_link_only(path), format="turtle")
    node = LG["ref-example-report"]
    assert (node, RDF.type, LGO.ExternalReference) in graph
    assert (node, LGO.supports, LG["DE-OLGK-2024-0119"]) in graph
    assert graph.value(node, LGO.excerpt) == Literal(
        "The regulator said refusing must be as easy as accepting.", lang="en"
    )


def test_link_only_refuses_a_long_quote(tmp_path: Path) -> None:
    path = tmp_path / "link-only.yaml"
    path.write_text(
        f"""
- id: too-long
  title: "t"
  publisher: "p"
  url: "https://example.org"
  why_link_only: "third-party work"
  quote: {{text: "{"word " * 80}", locator: "para. 1", language: en}}
"""
    )
    with pytest.raises(law_sources.SourceError, match="at most 300"):
        law_sources.extract_link_only(path)


INDEX = """
id: de/test
title: Test
jurisdiction: DE
language: de
kind: authored-xml
{licence}
originals:
  - file: page.html
    url: https://example.org/page.html
    fetch: file
    media_type: text/html
    retrieved_on: 2026-11-04
    sha256: 00
annotated: test.law.xml
"""


def test_a_licence_must_be_known_and_explained(tmp_path: Path) -> None:
    index = tmp_path / "source.yaml"
    index.write_text(INDEX.format(licence="licence: free-for-all\nlicence_basis: because"))
    with pytest.raises(law_sources.SourceError, match="licence must be one of"):
        law_sources.parse_index(index)
    index.write_text(INDEX.format(licence="licence: official-work"))
    with pytest.raises(law_sources.SourceError, match="licence_basis"):
        law_sources.parse_index(index)
    index.write_text(INDEX.format(licence='licence: official-work\nlicence_basis: "§ 5 Abs. 1 UrhG"'))
    source = law_sources.parse_index(index)
    assert (source.licence, source.licence_basis) == ("official-work", "§ 5 Abs. 1 UrhG")
    assert law_sources.LICENCES[source.licence] == LGV.OfficialWork
