import json

from rdflib import Graph, Literal

from legalgraph import LG, LGO, localisation, site
from legalgraph.load import DEFAULT_DATA_DIR, DEFAULT_ONTOLOGY_DIR, Sources, load_all

SOURCES = Sources(data_dir=DEFAULT_DATA_DIR, ontology_dir=DEFAULT_ONTOLOGY_DIR)


def test_site_data_covers_every_provision_with_its_pointers() -> None:
    counts = site.generate_data(SOURCES)
    provisions = {p["id"]: p for p in json.loads((site.DATA_DIR / "provisions.json").read_text())}
    assert counts["provisions"] == len(provisions)
    ddg = provisions["DE-DDG-s5-1"]
    assert ddg["act"] == "DE-DDG" and ddg["document"] == "DE-DDG-source"
    assert ddg["sourceElement"].startswith("/dokumente/")
    quote = ddg["quotes"][0]
    assert quote["translation"]["status"] == "Draft"
    assert len(quote["text"].splitlines()) == len(quote["translation"]["text"].splitlines())
    assert (site.PUBLIC_DIR / "id" / "DE-DDG-s5-1.ttl").exists()
    assert (site.PUBLIC_DIR / "id" / "DE-DDG-s5-1-q1-en.ttl").exists()
    assert (site.PUBLIC_DIR / "sources" / "de" / "ddg" / "source.yaml").exists()


def test_graph_view_edges_point_to_known_nodes() -> None:
    site.generate_data(SOURCES)
    graph = json.loads((site.DATA_DIR / "graph.json").read_text())
    nodes = {node["id"] for node in graph["nodes"]}
    assert all(edge["source"] in nodes and edge["target"] in nodes for edge in graph["edges"])


def test_a_translation_must_keep_the_quote_lines() -> None:
    data, _, _, _ = load_all(SOURCES)
    data.set((LG["DE-VSBG-s36-1-q1-en"], LGO.text, Literal("All on one line.", lang="en")))
    assert any("DE-VSBG-s36-1-q1-en" in error for error in localisation.line_mismatches(data))


def test_last_amended_comes_from_the_source_notes() -> None:
    graph = Graph()
    document = LG["X-source"]
    graph.add((LG["X"], LGO.sourceDocument, document))
    graph.add((document, LGO.legalStatus, Literal("Zuletzt geändert durch Art. 1 G v. 20.7.2026 I Nr. 215", lang="de")))
    graph.add(
        (
            document,
            LGO.legalStatus,
            Literal("Änderung durch Art. 3 G v. 3.10.2026 I Nr. 1 textlich nachgewiesen", lang="de"),
        )
    )
    assert site.last_amended(graph, LG["X"]) == "2026-10-03"
    eu = LG["EU-X-source"]
    graph.add((LG["EU-X"], LGO.sourceDocument, eu))
    graph.add(
        (
            eu,
            LGO.legalStatus,
            Literal(
                "Consolidated text applying from 27 September 2026, prepared by the Publications Office.", lang="en"
            ),
        )
    )
    assert site.last_amended(graph, LG["EU-X"]) == "2026-09-27"
    assert site.last_amended(graph, LG["Y"]) is None
