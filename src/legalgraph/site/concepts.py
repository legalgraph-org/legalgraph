"""The site's concepts collection (vocabulary terms, conditions, actions) and the rules layer."""

from typing import Any

from rdflib import RDF, SKOS, Graph
from rdflib.term import Node

from legalgraph import ELI, LG, LGO, LGV, rules, scenarios
from legalgraph.site.values import english_text, inverse, label, name, names, one, texts


def concepts(graph: Graph) -> list[dict[str, Any]]:
    result = []
    kinds = {
        LGO.InformationItem: "item",
        LGO.DisclosureType: "disclosure",
        LGO.LegalConcept: "concept",
        LGO.Condition: "condition",
        LGO.Action: "action",
        LGO.ActorRole: "role",
    }
    seen = set()
    for cls, kind in kinds.items():
        for concept in graph.subjects(RDF.type, cls):
            if concept in seen:
                continue
            seen.add(concept)
            result.append(concept_entry(graph, concept, kind))
    result += [
        concept_entry(graph, concept, "term")
        for concept in graph.subjects(RDF.type, SKOS.Concept)
        if concept not in seen and str(concept).startswith(str(LGV))
    ]
    return sorted(result, key=lambda c: (c["kind"], c["label"]))


def concept_entry(graph: Graph, concept: Node, kind: str) -> dict[str, Any]:
    return {
        "id": name(concept),
        "kind": kind,
        "scheme": label(graph, graph.value(concept, SKOS.inScheme)) if graph.value(concept, SKOS.inScheme) else None,
        "label": label(graph, concept),
        "labels": texts(graph, concept, SKOS.prefLabel),
        "altLabels": texts(graph, concept, SKOS.altLabel),
        "definition": english_text(graph, concept, SKOS.definition),
        "broader": names(graph, concept, SKOS.broader),
        "narrower": inverse(graph, concept, SKOS.broader),
        "requiredBy": [
            n for n in inverse(graph, concept, LGO.requiresDisclosureOf) if (LG[n], RDF.type, LGO.Provision) in graph
        ],
        "definedBy": inverse(graph, concept, LGO.defines),
        "regulatedBy": inverse(graph, concept, LGO.regulates),
        "enforcedBy": inverse(graph, concept, LGO.enforces),
        "explainedBy": inverse(graph, concept, LGO.explains),
        "question": english_text(graph, concept, LGO.question),
        "basedOn": names(graph, concept, LGO.basedOn),
        "holdsWhenAny": names(graph, concept, LGO.holdsWhenAny),
        "holdsWhenAll": names(graph, concept, LGO.holdsWhenAll),
        "usedBy": sorted(
            set(inverse(graph, concept, LGO.appliesWhen))
            | set(inverse(graph, concept, LGO.unless))
            | {
                n
                for n in inverse(graph, concept, LGO.requiresDisclosureOf)
                if (LG[n], RDF.type, LGO.Obligation) in graph
            }
            | set(inverse(graph, concept, LGO.requiresAction))
            | set(inverse(graph, concept, LGO.bearer))
        ),
    }


def obligations(graph: Graph) -> list[dict[str, Any]]:
    """The rules layer: obligations with their conditions, for the rule pages and the checklist."""
    _, found = rules.load(graph)
    return [
        {
            "id": o.id,
            "label": o.label,
            "comment": o.comment,
            "appliesIn": o.applies_in,
            "appliesWhen": o.applies_when,
            "unless": o.unless,
            "items": o.items,
            "actions": o.actions,
            "disclosure": o.disclosure,
            "establishedBy": o.established_by,
            "refines": o.refines,
            "implementedBy": o.implemented_by,
            # Whether it follows the business's markets rather than its establishment, and the
            # jurisdictions it applies in (rules.places).
            "marketBased": o.market_based,
            "within": sorted(o.within),
            "bearer": names(graph, LG[o.id], LGO.bearer),
            "deonticType": name(graph.value(LG[o.id], LGO.deonticType)),
            "reviewStatus": o.status,
            "cases": sorted(
                inverse(graph, LG[o.id], LGO.illustrates),
                key=lambda d: (one(graph, LG[d], ELI.date_document) or "", d),
                reverse=True,
            ),
            # Penalty provisions for a breach of the provisions the rule comes from.
            "penalties": sorted({name(p) for e in o.established_by for p in graph.subjects(LGO.penalises, LG[e])}),
        }
        for o in sorted(found.values(), key=lambda o: o.id)
    ]


def checklist_data(graph: Graph) -> dict[str, Any]:
    """What the checklist page evaluates in the browser: the conditions (asked or derived) and the
    scenarios, with the same rules as `legalgraph checklist`. Where the business is established and
    where it offers its services are jurisdictions: `within` lists those a condition tied to one holds for."""
    conditions, _ = rules.load(graph)
    places = rules.jurisdictions(graph)
    return {
        "conditions": [
            {
                "id": c.id,
                "label": c.label,
                "question": c.question,
                "anyOf": c.any_of,
                "allOf": c.all_of,
                "basedOn": c.based_on,
                "establishedIn": c.established_in,
                "offersIn": c.offered_in,
                "within": sorted(c.within),
            }
            for c in sorted(conditions.values(), key=lambda c: c.id)
        ],
        "jurisdictions": [{"id": j, "label": label} for j, label in sorted(places.items(), key=lambda x: x[1])],
        "markets": sorted({c.offered_in for c in conditions.values() if c.offered_in}),
        "scenarios": [
            {
                "id": s.path.stem,
                "name": s.name,
                "description": s.description,
                "facts": sorted(s.facts),
                "establishedIn": s.established_in,
                "markets": sorted(s.markets),
                # What the scenario must get: the site's tests check lib/checklist-rules.ts against it.
                "obligations": sorted(s.expected),
            }
            for s in scenarios.load_scenarios()
        ],
    }
