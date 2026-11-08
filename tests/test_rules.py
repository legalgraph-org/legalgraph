import pytest

from legalgraph import rules
from legalgraph.load import DEFAULT_DATA_DIR, DEFAULT_ONTOLOGY_DIR, Sources, load_all, new_graph


@pytest.fixture(scope="module")
def graph():
    data, ontology, _, errors = load_all(Sources(DEFAULT_DATA_DIR, DEFAULT_ONTOLOGY_DIR))
    assert not errors
    merged = new_graph()
    merged += data
    merged += ontology
    return merged


@pytest.fixture(scope="module")
def loaded(graph) -> tuple[dict[str, rules.Condition], dict[str, rules.Obligation]]:
    return rules.load(graph)


@pytest.mark.parametrize("scenario", rules.load_scenarios(), ids=lambda s: s.path.stem)
def test_scenarios_get_exactly_their_obligations(graph, loaded, scenario: rules.Scenario) -> None:
    conditions, obligations = loaded
    places = rules.jurisdictions(graph)
    assert {scenario.established_in} - {None} | scenario.markets <= set(places)
    found = rules.applicable(conditions, obligations, scenario.facts, scenario.established_in, scenario.markets)
    ids = {o.id for o in found}
    assert ids == scenario.expected, (
        f"missing {sorted(scenario.expected - ids)}, unexpected {sorted(ids - scenario.expected)}"
    )
    for obligation in found:
        if obligation.id in scenario.national:
            assert set(obligation.national(scenario.established_in)) == scenario.national[obligation.id], obligation.id


def test_derived_conditions(loaded) -> None:
    conditions, _ = loaded
    holds = rules.holding(conditions, {"ProcessesPersonalData", "CommercialDigitalService"}, established_in="DE")
    assert {"EstablishedInGermany", "EstablishedInTheUnion", "EstablishedInTheEea", "GdprApplies"} <= holds
    assert "GdprApplies" not in rules.holding(conditions, set(), established_in="DE")


def test_establishment_holds_for_the_jurisdictions_containing_it(loaded) -> None:
    conditions, _ = loaded
    austria = rules.holding(conditions, set(), established_in="AT")
    assert {"EstablishedInTheUnion", "EstablishedInTheEea"} <= austria and "EstablishedInGermany" not in austria
    norway = rules.holding(conditions, set(), established_in="NO")
    assert "EstablishedInTheEea" in norway and "EstablishedInTheUnion" not in norway
    assert "OffersGoodsOrServicesInTheUnion" in rules.holding(conditions, set(), markets={"FR"})


def test_an_establishment_fact_stands_for_the_jurisdiction(loaded) -> None:
    conditions, obligations = loaded
    facts = {"EstablishedInGermany", "CommercialDigitalService"}
    assert "EstablishedInTheEea" in rules.holding(conditions, facts)
    found = {o.id for o in rules.applicable(conditions, obligations, facts)}
    assert found == {o.id for o in rules.applicable(conditions, obligations, facts - {"EstablishedInGermany"}, "DE")}


def test_a_national_rule_replaces_the_rule_it_refines(loaded) -> None:
    conditions, obligations = loaded
    germany = {o.id for o in rules.applicable(conditions, obligations, {"CommercialDigitalService"}, "DE")}
    assert "DE-R-impressum" in germany and "EU-R-service-provider-information" not in germany
    austria = {o.id for o in rules.applicable(conditions, obligations, {"CommercialDigitalService"}, "AT")}
    assert "EU-R-service-provider-information" in austria


def test_a_directive_rule_names_the_national_provision(loaded) -> None:
    _, obligations = loaded
    rule = obligations["EU-R-service-provider-information"]
    assert rule.national("AT") == ["AT-ECG-s5-1"]
    assert rule.national("DE") == ["DE-DDG-s5-1"]
    assert rule.national("MT") == ["MT-CAP426-art8C-1"]
    assert rule.national("NO") == ["NO-EHL-s8-1"] and rule.national(None) == []


def test_refinements_are_narrower(loaded) -> None:
    """A refining rule applies only where the rule it refines does, or it would hide a rule that applies."""
    conditions, obligations = loaded
    for obligation in obligations.values():
        for general in obligation.refines:
            facts = {c for c in obligation.applies_when if not conditions[c].established_in}
            holds = rules.holding(
                conditions, facts, rules.establishment(conditions, set(obligation.applies_when), None)
            )
            assert all(c in holds for c in obligations[general].applies_when), (obligation.id, general)


def test_an_exemption_switches_an_obligation_off(loaded) -> None:
    conditions, obligations = loaded
    facts = {"EstablishedInGermany", "SellsToConsumers"}
    assert "DE-R-dispute-resolution-statement" in {o.id for o in rules.applicable(conditions, obligations, facts)}
    exempt = rules.applicable(conditions, obligations, facts | {"TenOrFewerEmployees"})
    assert "DE-R-dispute-resolution-statement" not in {o.id for o in exempt}


def test_unknown_facts_are_rejected(loaded) -> None:
    conditions, obligations = loaded
    with pytest.raises(rules.RulesError, match="NoSuchCondition"):
        rules.applicable(conditions, obligations, {"NoSuchCondition"})


def test_every_condition_can_be_answered(loaded) -> None:
    """A rule's conditions must be askable, or derivable from askable ones, or a checklist can never
    reach it."""
    conditions, obligations = loaded
    places = {c.id for c in conditions.values() if c.established_in or c.offered_in}
    reachable = rules.holding(conditions, {c.id for c in rules.asked(conditions)} | places)
    for obligation in obligations.values():
        for condition in obligation.applies_when + obligation.unless:
            assert condition in reachable, (obligation.id, condition)


def test_every_rule_traces_to_the_law(loaded) -> None:
    conditions, obligations = loaded
    for obligation in obligations.values():
        assert obligation.established_by, obligation.id
        for condition in obligation.applies_when + obligation.unless:
            current = conditions[condition]
            assert current.based_on or current.any_of or current.all_of or current.established_in, condition
