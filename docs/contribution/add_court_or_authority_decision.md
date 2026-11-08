# Add a court or authority decision

Decisions show the law at work: how a court read a provision, what a regulator fined and why. A
decision enters the graph in two parts.

## 1. The decision's text is a source

Add it like any other source ([Add a new source](add_new_source.md)): the court's or authority's own
publication, fetched and kept byte for byte, with a `licence` (court decisions are official works
in most countries; see [Licences](licences_and_link_only.md)).

On the root element, `lga:act-type` is `Judgment` for a court and `AuthorityDecision` for a
regulator's decision in an individual case (a fine, an order). Quote the points that matter:

- the **operative part** (Tenor, dispositif, ruling): what was ordered;
- the **reasons** that state how a provision was read (`lga:interprets`) or applied to the facts
  (`lga:applies`);
- headnotes, where the court wrote them itself.

Each quoted point is a provision of the decision, annotated like any other
([Annotations](annotations.md)). Quote the decision's own words, including its redactions.

## 2. The case: number, outcomes, rules

What the decision ordered is not annotated in the XML. It is written by hand in
`data/cases/<country>.ttl`:

```turtle
lg:DE-OLGK-2024-0119 lgo:caseNumber "6 U 80/23" ;
    lgo:hasOutcome lg:DE-OLGK-2024-0119-outcome-1 ;
    lgo:illustrates lg:DE-R-cookie-consent .

lg:DE-OLGK-2024-0119-outcome-1 a lgo:Outcome ;
    lgo:outcomeType lgv:Injunction ;
    lgo:against "The operator of a news portal (name redacted in the published judgment)" ;
    lgo:statedIn lg:DE-OLGK-2024-0119-tenor-1 ;
    lgo:forBreachOf lg:DE-TDDDG-s25-1 ;
    lgo:reviewStatus lgv:SourceChecked .
```

| Property | Meaning |
|---|---|
| `lgo:caseNumber` | The reference as the court or authority writes it: `C-40/17`, `6 U 80/23`, `SAN-2021-023` |
| `lgo:hasOutcome` | What followed for a party |
| `lgo:outcomeType` | `Fine`, `Damages`, `Injunction`, `ComplianceOrder`, `Settlement`, `FindingOfInfringement` |
| `lgo:against` | The party, as the decision names it |
| `lgo:amount`, `lgo:currency` | For fines, damages and settlements |
| `lgo:statedIn` | **Required.** The quoted point of this decision that states the outcome, so the party and amount can be checked against its words |
| `lgo:forBreachOf` | The provision that was breached |
| `lgo:sanctionedUnder` | The provision the sanction rests on (a penalty provision, a liability provision) |
| `lgo:illustrates` | The rules of the graph the decision shows at work |
| `lgo:follows` | An earlier decision it follows (a national court after a Court of Justice ruling) |
| `lgo:readUnder` | On a point: a repealed provision it was decided under, when a provision in the graph continues it (`lgo:continues`) |

Check each legal basis against the reasons. If the court says the claim rests on § 823 Abs. 1 BGB,
`sanctionedUnder` is § 823 Abs. 1, not a provision that seems to fit.

## Parties

Name parties as the published decision names them. Where the publisher has redacted or anonymised
them ("[X]", "the defendant"), the graph does too. If an earlier publication named them, link it in
`sources/link-only.yaml` so the fact stays checkable, but don't copy the named text
([Link-only sources](licences_and_link_only.md#link-only-sources)).

## Press releases and news

A regulator's press release or a news report can add context the decision lacks: how an order was
later closed, how a fine was split. Link it through `sources/link-only.yaml`, with the decision's
identifier in `supports`.

`make check` validates every outcome: it must be stated in a point of its own decision, and only
decisions may have outcomes or illustrate rules.
