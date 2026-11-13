"""The rules layer: which obligations apply to a business, given facts about it.

An obligation (lgo:Obligation, data/rules/) applies when all its lgo:appliesWhen conditions hold and
none of its lgo:unless conditions does. Facts are the conditions known to hold (answers to the
conditions' questions); a derived condition also holds when any (lgo:holdsWhenAny) or all
(lgo:holdsWhenAll) of its conditions do. Where the business is established and where it offers its
services are jurisdictions: a condition tied to one (lgo:establishedIn, lgo:offersIn) holds for it and
every jurisdiction within it. A business also offers its services where it is established.

A rule follows either the business's establishment (the e-Commerce Directive's country-of-origin
principle: provider information, contract terms) or its markets, when one of its conditions is tied to
where the business offers its services (consumer contracts follow the consumer's country, Article 6
Rome I). National obligations that refine a general one (lgo:refines) replace it when every place the
general one is followed in lies within their jurisdictions: a German shop selling only in Germany gets
the German rule, one also selling to Italy keeps the EU rule beside it. For a general
rule resting on a directive, the national provisions implementing it are named for those places.
Everything a checklist says points to the obligation and the provisions it comes from.

Scenarios (legalgraph.scenarios) are example businesses with the obligations they must get.
"""

from dataclasses import dataclass, field

from rdflib import RDF, RDFS, Graph, Literal, URIRef
from rdflib.term import Node

from legalgraph import ELI, LG, LGO, LGV


class RulesError(Exception):
    pass


def local(node: Node) -> str:
    text = str(node)
    for namespace in (LG, LGV):
        if text.startswith(str(namespace)):
            return text.removeprefix(str(namespace))
    return text


def english(graph: Graph, subject: Node, predicate: URIRef) -> str | None:
    values = [o for o in graph.objects(subject, predicate) if isinstance(o, Literal)]
    preferred = [v for v in values if v.language in (None, "en")]
    return str(sorted(preferred or values, key=str)[0]) if values else None


@dataclass
class Condition:
    id: str
    label: str
    question: str | None
    any_of: list[str] = field(default_factory=list)
    all_of: list[str] = field(default_factory=list)
    based_on: list[str] = field(default_factory=list)
    established_in: str | None = None
    offered_in: str | None = None
    # The jurisdiction it is tied to and every jurisdiction within it.
    within: frozenset[str] = frozenset()


@dataclass
class Obligation:
    id: str
    label: str
    comment: str | None
    applies_in: str
    applies_when: list[str]
    unless: list[str]
    items: list[str]
    actions: list[str]
    disclosure: str | None
    established_by: list[str]
    status: str
    refines: list[str] = field(default_factory=list)
    # Provisions implementing those it is established by, by the jurisdiction of their act.
    implemented_by: dict[str, list[str]] = field(default_factory=dict)
    # The jurisdiction it applies in and every jurisdiction within it.
    within: frozenset[str] = frozenset()
    # Whether it follows the business's markets rather than its establishment.
    market_based: bool = False

    def national(self, jurisdiction: str | None) -> list[str]:
        """The provisions of this jurisdiction that implement the obligation's provisions."""
        return self.implemented_by.get(jurisdiction, []) if jurisdiction else []


def names(graph: Graph, subject: Node, predicate: URIRef) -> list[str]:
    return sorted(local(o) for o in graph.objects(subject, predicate))


def jurisdictions(graph: Graph) -> dict[str, str]:
    """Every jurisdiction with its English name."""
    found = {}
    for kind in (LGO.Country, LGO.Subdivision, LGO.SupranationalOrganisation):
        for node in graph.subjects(RDF.type, kind):
            found[local(node)] = english(graph, node, RDFS.label) or local(node)
    return found


def contained(graph: Graph, jurisdiction: Node) -> frozenset[str]:
    """The jurisdiction and those within it: its members and subdivisions, and theirs."""
    found, todo = set(), [jurisdiction]
    while todo:
        node = todo.pop()
        if local(node) in found:
            continue
        found.add(local(node))
        todo.extend(graph.subjects(LGO.memberOf, node))
        todo.extend(graph.subjects(LGO.subdivisionOf, node))
    return frozenset(found)


def implementations(graph: Graph, provisions: list[str]) -> dict[str, list[str]]:
    """Provisions implementing any of these, by the jurisdiction of their act."""
    found: dict[str, set[str]] = {}
    for provision in provisions:
        for national in graph.subjects(LGO.implements, LG[provision]):
            act = graph.value(national, ELI.is_part_of)
            jurisdiction = graph.value(act, LGO.jurisdiction) if act else None
            if jurisdiction is not None:
                found.setdefault(local(jurisdiction), set()).add(local(national))
    return {j: sorted(p) for j, p in sorted(found.items())}


def tied_to_markets(conditions: dict[str, Condition], condition: str, seen: frozenset[str] = frozenset()) -> bool:
    """Whether a condition depends on where the business offers its services, directly or through the
    conditions it is derived from."""
    current = conditions.get(condition)
    if current is None or condition in seen:
        return False
    if current.offered_in:
        return True
    return any(tied_to_markets(conditions, c, seen | {condition}) for c in current.any_of + current.all_of)


def load(graph: Graph) -> tuple[dict[str, Condition], dict[str, Obligation]]:
    """Conditions and obligations from a graph holding the data and the ontology."""
    conditions = {}
    for node in set(graph.subjects(RDF.type, LGO.Condition)):
        established_in = graph.value(node, LGO.establishedIn)
        offered_in = graph.value(node, LGO.offersIn)
        place = established_in or offered_in
        conditions[local(node)] = Condition(
            id=local(node),
            label=english(graph, node, URIRef("http://www.w3.org/2004/02/skos/core#prefLabel")) or local(node),
            question=english(graph, node, LGO.question),
            any_of=names(graph, node, LGO.holdsWhenAny),
            all_of=names(graph, node, LGO.holdsWhenAll),
            based_on=names(graph, node, LGO.basedOn),
            established_in=local(established_in) if established_in else None,
            offered_in=local(offered_in) if offered_in else None,
            within=contained(graph, place) if place else frozenset(),
        )
    obligations = {}
    for node in set(graph.subjects(RDF.type, LGO.Obligation)):
        obligations[local(node)] = Obligation(
            id=local(node),
            label=english(graph, node, RDFS.label) or local(node),
            comment=english(graph, node, RDFS.comment),
            applies_in=local(graph.value(node, LGO.appliesIn)),
            applies_when=names(graph, node, LGO.appliesWhen),
            unless=names(graph, node, LGO.unless),
            items=names(graph, node, LGO.requiresDisclosureOf),
            actions=names(graph, node, LGO.requiresAction),
            disclosure=local(graph.value(node, LGO.partOfDisclosure))
            if graph.value(node, LGO.partOfDisclosure)
            else None,
            established_by=names(graph, node, LGO.establishedBy),
            status=local(graph.value(node, LGO.reviewStatus)),
            refines=names(graph, node, LGO.refines),
            implemented_by=implementations(graph, names(graph, node, LGO.establishedBy)),
            within=contained(graph, graph.value(node, LGO.appliesIn)),
        )
    for obligation in obligations.values():
        obligation.market_based = any(tied_to_markets(conditions, c) for c in obligation.applies_when)
    return conditions, obligations


def establishment(conditions: dict[str, Condition], facts: set[str], established_in: str | None) -> str | None:
    """Where the business is established: as given, or from a fact such as EstablishedInGermany (the
    narrowest, if several are given)."""
    if established_in:
        return established_in
    places = [conditions[f] for f in facts if f in conditions and conditions[f].established_in]
    return min(places, key=lambda c: len(c.within)).established_in if places else None


def offered_in(established_in: str | None, markets: set[str] | frozenset[str]) -> set[str]:
    """Where the business offers its services: its markets and the place it is established in."""
    return set(markets) | ({established_in} if established_in else set())


def holding(
    conditions: dict[str, Condition],
    facts: set[str],
    established_in: str | None = None,
    markets: set[str] | frozenset[str] = frozenset(),
) -> set[str]:
    """The conditions that hold: the facts, those tied to where the business is established or offers
    its services, and every derived condition they imply."""
    unknown = facts - set(conditions)
    if unknown:
        raise RulesError(f"Unknown condition(s): {', '.join(sorted(unknown))}")
    established_in = establishment(conditions, facts, established_in)
    markets = offered_in(established_in, markets)
    holds = set(facts)
    for condition in conditions.values():
        if condition.established_in and established_in in condition.within:
            holds.add(condition.id)
        if condition.offered_in and condition.within & set(markets):
            holds.add(condition.id)
    changed = True
    while changed:
        changed = False
        for condition in conditions.values():
            if condition.id in holds:
                continue
            if (condition.any_of and any(c in holds for c in condition.any_of)) or (
                condition.all_of and all(c in holds for c in condition.all_of)
            ):
                holds.add(condition.id)
                changed = True
    return holds


def applicable(
    conditions: dict[str, Condition],
    obligations: dict[str, Obligation],
    facts: set[str],
    established_in: str | None = None,
    markets: set[str] | frozenset[str] = frozenset(),
) -> list[Obligation]:
    """The obligations that apply. One refined by others that apply too is left out when every place it
    is followed in lies within their jurisdictions."""
    holds = holding(conditions, facts, established_in, markets)
    established_in = establishment(conditions, facts, established_in)
    found = [
        o
        for o in obligations.values()
        if all(c in holds for c in o.applies_when) and not any(c in holds for c in o.unless)
    ]

    def replaced(general: Obligation) -> bool:
        refining = [o for o in found if general.id in o.refines]
        covered = set().union(*(o.within for o in refining))
        return bool(refining) and set(places(general, established_in, markets)) <= covered

    return sorted(
        (o for o in found if not replaced(o)),
        key=lambda o: (o.applies_in, o.disclosure or "~", o.id),
    )


def places(obligation: Obligation, established_in: str | None, markets: set[str] | frozenset[str]) -> list[str]:
    """Where the business follows the obligation, within the obligation's own jurisdiction: its markets
    for a market-based one, else the place it is established in."""
    where = offered_in(established_in, markets) if obligation.market_based else {established_in} - {None}
    return sorted(p for p in where if p in obligation.within)


def national(
    obligation: Obligation, established_in: str | None, markets: set[str] | frozenset[str]
) -> dict[str, list[str]]:
    """The national provisions implementing the obligation, for each place the business follows it in."""
    return {p: obligation.national(p) for p in places(obligation, established_in, markets) if obligation.national(p)}


def asked(conditions: dict[str, Condition]) -> list[Condition]:
    """The conditions a checklist asks about: those with a question."""
    return sorted((c for c in conditions.values() if c.question), key=lambda c: c.id)
