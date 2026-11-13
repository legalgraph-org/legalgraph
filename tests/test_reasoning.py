"""The ontology's logical rules on small graphs: what the reasoning rules infer, and what the shapes
built on them catch."""

import pytest
from rdflib import Graph

from legalgraph import LG, LGO
from legalgraph.load import DEFAULT_DATA_DIR, DEFAULT_ONTOLOGY_DIR, Sources, load_all
from legalgraph.reasoning import infer, load_rules, stated_inferences
from legalgraph.validate import shacl_results

PREFIXES = """
@prefix lg:   <https://legalgraph.org/id/> .
@prefix lgo:  <https://legalgraph.org/ontology#> .
@prefix lgv:  <https://legalgraph.org/vocab/> .
@prefix eli:  <http://data.europa.eu/eli/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
"""

JURISDICTIONS = """
lg:EEA a lgo:SupranationalOrganisation ; lgo:isoCode "EEA" ; rdfs:label "EEA"@en .
lg:EU a lgo:SupranationalOrganisation ; lgo:isoCode "EU" ; rdfs:label "EU"@en ; lgo:memberOf lg:EEA .
lg:DE a lgo:Country ; lgo:isoCode "DE" ; rdfs:label "Germany"@en ; lgo:memberOf lg:EU .
lg:US a lgo:Country ; lgo:isoCode "US" ; rdfs:label "United States"@en .
lg:US-CA a lgo:Subdivision ; lgo:isoCode "US-CA" ; rdfs:label "California"@en ; lgo:subdivisionOf lg:US .
"""


@pytest.fixture(scope="module")
def ontology() -> tuple[Graph, Graph, Graph]:
    sources = Sources(data_dir=DEFAULT_DATA_DIR, ontology_dir=DEFAULT_ONTOLOGY_DIR)
    _, ontology, shapes, errors = load_all(sources)
    assert not errors
    return ontology, shapes, load_rules(sources)


def graph(turtle: str) -> Graph:
    return Graph().parse(data=PREFIXES + turtle, format="turtle")


def test_a_jurisdiction_lies_within_itself_and_whatever_it_is_part_of(ontology) -> None:
    ontology_graph, _, rules = ontology
    inferred = infer(graph(JURISDICTIONS) + ontology_graph, rules)
    within = {(s.removeprefix(LG), o.removeprefix(LG)) for s, o in inferred.subject_objects(LGO.within)}
    assert {("DE", "DE"), ("DE", "EU"), ("DE", "EEA"), ("EU", "EEA"), ("US-CA", "US")} <= within
    assert ("EEA", "EU") not in within and ("US", "US-CA") not in within


def test_inferring_leaves_the_input_graph_alone(ontology) -> None:
    _, _, rules = ontology
    data = graph(JURISDICTIONS)
    infer(data, rules)
    assert not list(data.subject_objects(LGO.within))


def test_the_data_may_not_state_an_inferred_property(ontology) -> None:
    ontology_graph, _, _ = ontology
    data = graph(JURISDICTIONS + "lg:DE lgo:within lg:EU .")
    assert stated_inferences(data, ontology_graph) == ["lg:DE states lgo:within, which only the reasoning rules infer"]


def obligation(name: str, place: str, extra: str = "") -> str:
    return f"""
lg:{name} a lgo:Obligation ; rdfs:label "{name}"@en ; lgo:appliesIn lg:{place} ;
    lgo:establishedBy lg:P ; lgo:bearer lgv:DigitalServiceProvider ; lgo:deonticType lgv:Must ;
    lgo:reviewStatus lgv:Draft {extra} .
"""


PROVISION = """
lg:ACT a lgo:LegalAct ; lgo:jurisdiction lg:DE .
lg:P a lgo:Provision ; eli:is_part_of lg:ACT ; lgo:citation "§ 1" ; lgo:reviewStatus lgv:Draft .
"""


def messages(ontology, turtle: str) -> tuple[list[str], list[str]]:
    ontology_graph, shapes, rules = ontology
    return shacl_results(graph(JURISDICTIONS + PROVISION + turtle), ontology_graph, shapes, rules)


def test_a_national_rule_may_refine_one_of_a_wider_jurisdiction(ontology) -> None:
    violations, _ = messages(
        ontology, obligation("GENERAL", "EU") + obligation("NATIONAL", "DE", "; lgo:refines lg:GENERAL")
    )
    assert not [v for v in violations if "refining obligation" in v]


def test_a_rule_cannot_refine_one_of_a_narrower_jurisdiction(ontology) -> None:
    violations, _ = messages(
        ontology, obligation("NATIONAL", "DE") + obligation("GENERAL", "EU", "; lgo:refines lg:NATIONAL")
    )
    assert [v for v in violations if "refining obligation" in v] == [
        "lg:GENERAL (lg:NATIONAL): A refining obligation applies within the jurisdiction of the obligation it refines."
    ]


def test_an_item_no_provision_asks_for_is_a_warning(ontology) -> None:
    violations, warnings = messages(ontology, obligation("RULE", "DE", "; lgo:requiresDisclosureOf lgv:VatId"))
    assert not [v for v in violations if "lgv:VatId" in v]
    assert "lg:RULE (lgv:VatId): No provision the obligation is established by asks for this item." in warnings


def test_an_item_a_point_of_the_provision_asks_for_is_grounded(ontology) -> None:
    point = """
lg:P-a a lgo:Provision ; eli:is_part_of lg:P ; lgo:citation "§ 1 a" ; lgo:reviewStatus lgv:Draft ;
    lgo:requiresDisclosureOf lgv:VatId .
"""
    _, warnings = messages(ontology, point + obligation("RULE", "DE", "; lgo:requiresDisclosureOf lgv:VatId"))
    assert not [w for w in warnings if "lg:RULE" in w]


def test_an_implementing_act_should_say_what_it_transposes(ontology) -> None:
    eu = """
lg:DIR a lgo:LegalAct ; lgo:jurisdiction lg:EU .
lg:Q a lgo:Provision ; eli:is_part_of lg:DIR ; lgo:citation "Art. 1" ; lgo:reviewStatus lgv:Draft .
lg:P lgo:implements lg:Q .
"""
    _, warnings = messages(ontology, eu)
    assert [w for w in warnings if "eli:transposes" in w] == [
        "lg:P (lg:DIR): The act of a provision that implements another act's provision should state "
        "eli:transposes for that act."
    ]
    _, warnings = messages(ontology, eu + "lg:ACT eli:transposes lg:DIR .")
    assert not [w for w in warnings if "eli:transposes" in w]
