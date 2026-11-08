from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import Graph, Literal

from legalgraph import ELI, LG, LGO, LGV, localisation
from legalgraph.cli import QUERIES_DIR, cli, run_query
from legalgraph.load import DEFAULT_DATA_DIR, DEFAULT_ONTOLOGY_DIR, Sources, load_all
from legalgraph.validate import validate


@pytest.fixture(scope="session")
def sources() -> Sources:
    return Sources(data_dir=DEFAULT_DATA_DIR, ontology_dir=DEFAULT_ONTOLOGY_DIR)


@pytest.fixture(scope="session")
def data(sources: Sources) -> Graph:
    graph, _, _, errors = load_all(sources)
    assert not errors
    return graph


def test_graph_is_valid(sources: Sources) -> None:
    report = validate(sources)
    assert report.ok, "\n".join(report.errors)


def test_validation_catches_a_dangling_reference(sources: Sources, tmp_path: Path) -> None:
    (tmp_path / "bad.ttl").write_text(
        (DEFAULT_DATA_DIR / "jurisdictions.ttl").read_text()
        + "\nmlg:XX-ACT a lgo:LegalAct ; lgo:jurisdiction lg:NOWHERE .\n"
    )
    report = validate(Sources(data_dir=tmp_path, ontology_dir=sources.ontology_dir))
    assert any("NOWHERE" in error for error in report.errors)


def test_every_country_of_the_research_is_present(data: Graph) -> None:
    countries = set(data.subjects(predicate=None, object=LGO.Country))
    # the 39 European countries of the research, plus the UK, Ukraine, the US and Canada
    assert len(countries) == 39 + 4
    assert {LG["GB"], LG["UA"], LG["US"], LG["CA"]} <= countries


def test_source_checked_quotes_come_from_https_sources(data: Graph) -> None:
    for quote in data.subjects(object=LGO.Quote):
        provision = data.value(quote, LGO.quoteOf)
        assert data.value(provision, LGO.reviewStatus) == LGV.SourceChecked, quote
        source = str(data.value(quote, LGO.sourceUrl))
        assert source.startswith(("https://", "http://")), quote


@pytest.mark.parametrize("query", sorted(path.stem for path in QUERIES_DIR.glob("*.rq")))
def test_example_queries_return_rows(sources: Sources, query: str) -> None:
    data, ontology, _, _ = load_all(sources)
    columns, rows = run_query(data + ontology, (QUERIES_DIR / f"{query}.rq").read_text())
    assert columns and rows


def test_quotes_command_filters_by_country() -> None:
    result = CliRunner().invoke(cli, ["quotes", "--country", "AT"])
    assert result.exit_code == 0, result.output
    assert "§ 5 Abs. 1 ECG" in result.output
    assert "DDG" not in result.output
    assert "English (Draft):" in result.output


def test_every_non_english_quote_has_a_current_translation(sources: Sources) -> None:
    data, ontology, _, _ = load_all(sources)
    assert localisation.pending(data, ontology) == []


def test_changing_a_quote_makes_its_translation_stale(sources: Sources) -> None:
    data, ontology, _, _ = load_all(sources)
    quote = LG["DE-VSBG-s36-3-q1"]
    data.set((quote, LGO.text, Literal("(3) Geänderter Text des Absatzes zu Testzwecken.", lang="de")))
    items = localisation.pending(data, ontology)
    assert [(item.subject, item.reason) for item in items] == [(str(quote), "stale")]


def test_non_english_title_without_english_is_reported(sources: Sources) -> None:
    data, ontology, _, _ = load_all(sources)
    act = LG["XX-TEST"]
    data.add((act, ELI.title, Literal("Gesetz zu Testzwecken", lang="de")))
    items = localisation.pending(data, ontology)
    assert [(item.subject, item.kind) for item in items] == [(str(act), "literal")]


def test_apply_writes_draft_translations(tmp_path: Path) -> None:
    item = localisation.WorkItem(
        kind="quote",
        subject=str(LG["DE-TEST-q1"]),
        lang="de",
        text='(1) Ein "Test".\n2. Zeile',
        sha256=localisation.sha256('(1) Ein "Test".\n2. Zeile'),
        reason="missing",
        translation='(1) A "test".\n2. Line',
    )
    literal = localisation.WorkItem(
        kind="literal",
        subject=str(LG["DE-TEST"]),
        lang="de",
        text="Testgesetz",
        sha256=localisation.sha256("Testgesetz"),
        reason="missing",
        predicate=str(ELI.title),
        translation="Test Act",
    )
    localisation.apply(tmp_path, [item, literal], "test-model", "machine", date(2026, 10, 31))
    graph = Graph()
    for path in (tmp_path / "translations" / "en").glob("*.ttl"):
        graph.parse(path, format="turtle")
    node = LG["DE-TEST-q1-en"]
    assert str(graph.value(node, LGO.text)) == '(1) A "test".\n2. Line'
    assert graph.value(node, LGO.reviewStatus) == LGV.Draft
    assert graph.value(node, LGO.translationMethod) == LGV.MachineTranslation
    title = localisation.translation_iri(str(LG["DE-TEST"]), str(ELI.title), literal.sha256)
    assert graph.value(title, LGO.translatedProperty) == ELI.title
    assert graph.value(title, LGO.text) == Literal("Test Act", lang="en")


def test_an_official_language_version_needs_no_translation(sources: Sources) -> None:
    data, ontology, _, _ = load_all(sources)
    german = LG["EU-2016-679-art13-1-q1-de"]
    assert (german, LGO.languageVersionOf, LG["EU-2016-679-art13-1-q1"]) in data
    assert not any(item.subject == str(german) for item in localisation.pending(data, ontology))
