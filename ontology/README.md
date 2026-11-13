# legalgraph ontology

The classes, properties, vocabularies and validation shapes behind the
[legalgraph](../README.md) in this repository: an open knowledge graph of the laws that tell
businesses what they must disclose on websites and in marketing.

Maintained by [Aimix GmbH](https://aimix.io). Aimix are researchers, not lawyers; nothing here is legal
advice.

## Layout

```
ontology.ttl               the ontology's header (owl:Ontology, version)
classes/<ClassName>.ttl    one file per class, with the properties whose domain it is
properties/<name>.ttl      one file per property without a single class as its domain
vocab/
  act-types.ttl            directive, regulation, statute, code, decree, judgment, guidelines …
  disclosure-types.ttl     Impressum, privacy information, pre-contractual information, accessibility, AI transparency …
  information-items.ttl    name, address, VAT ID, purposes, legal basis, retention, total price …
  legal-concepts.ttl       personal data, consent, lawful bases, scope criteria, cookies, order button …
  conditions.ttl           facts rules depend on, each with a checklist question
  actions.ttl              what rules require beyond disclosure (obtain consent, label the order button …)
  actor-roles.ttl          provider of a digital service, controller, trader, advertiser
  deontic-types.ttl        must, must not, may
  review-status.ttl        Source checked / Draft / Reviewed
  translation-methods.ttl  machine, human, official translation
annotations/
  localisation.ttl         which properties need an English (@en) value
rules/
  reasoning/<Name>.ttl     SHACL rules (sh:rule) that add inferred triples before validation
  validation/<Name>.ttl    SHACL shapes every graph must conform to, one per file
```

The files in `classes/` are the list of classes. `legalgraph hygiene` keeps the layout: each class
alone in a file named after it, each property next to its class, each shape or rule in a file named
after it, and no other folders.

Validation runs in two steps. First the rules in `rules/reasoning/` add what follows from the graph,
for example `lgo:within` (a jurisdiction lies within itself and whatever it is a member or
subdivision of); a property marked `lgo:inferred true` only ever comes from these rules, never from
the data. Then the shapes in `rules/validation/` check the data together with the inferred triples.
A shape with `sh:severity sh:Warning` reports a gap without failing validation, for example an act
whose provisions implement a directive but that does not state `eli:transposes` for it.

The ontology describes the model; it holds no facts about specific laws. Those live in `data/` of
this repository. Its version is `owl:versionInfo` in `ontology.ttl`.

## Model

```
Jurisdiction ◄─ jurisdiction ── LegalAct ◄─ eli:is_part_of ── Provision ◄─ quoteOf ── Quote
 (Country,                        │  eli:transposes             │  implements ──► Provision (EU)
  SupranationalOrganisation)      ▼                             │  regulates ──► DisclosureType
  memberOf ─► EU / EEA         LegalAct (EU)                    └─ requiresDisclosureOf ──► InformationItem

Quote ◄─ translationOf ── Translation (@en text, method, translatedBy, translatedOn, sourceTextSha256, reviewStatus)

LegalAct / Provision / Quote ── sourceDocument ──► SourceDocument (repositoryPath, sha256, sourceUrl, retrievedOn)
                             └─ sourceElement "XPath of the element in that document"

LegalAct ── amendmentCheck ──► AmendmentCheck (checkedOn, sourceUrl, lastKnownAmendment, lastKnownAmendmentDate,
                                lastKnownAmendmentInForce, sourceIsCurrent)

Quote ── languageVersionOf ──► Quote          (the same provision in another official language)
LegalDocument = LegalAct | CourtDecision (ecli) | Guidance
Provision ── interprets / specifies / takesPrecedenceOver / refersTo / implements ──► Provision
Provision ── explains ──► LegalConcept         (recitals)

Obligation ── establishedBy ──► Provision      (rules: the normative layer)
   ├─ bearer ──► ActorRole        ├─ appliesWhen ──► Condition (all)   ├─ unless ──► Condition (any)
   ├─ requiresDisclosureOf ──► InformationItem   ├─ requiresAction ──► Action
   └─ partOfDisclosure ──► DisclosureType, appliesIn ──► Jurisdiction, deonticType ──► must / must not / may
Condition ── holdsWhenAny / holdsWhenAll ──► Condition, basedOn ──► Provision, question "…?"
```

An `AmendmentCheck` records the latest amendment *known to the graph* and the day it was last
looked up at an official source. It does not claim the act has not changed since; an act
without a check says nothing about how current it is.

Text in other languages is always paired with English. Quotes are translated through
`lgo:Translation` nodes, which keep provenance and go stale when the quote changes; short literals
on properties marked `lgo:englishRequired` get an `@en` sibling.

It borrows from established standards rather than reinventing them:

- **[ELI](http://data.europa.eu/eli/ontology)** (European Legislation Identifier):
  `lgo:LegalAct` and `lgo:Provision` subclass `eli:LegalResource` and `eli:LegalResourceSubdivision`,
  and the graph uses `eli:title`, `eli:is_part_of`, `eli:transposes`, `eli:repeals`,
  `eli:date_document` and the in-force dates directly.
- **FRBR**: a `LegalAct` is the *Work*. Versions and language *Expressions* come in a later version.
- **SKOS** for the controlled vocabularies, so labels can be localised and terms mapped to other
  schemes.
- **LKIF**: the normative layer follows its norm module (obligations with bearers, conditions,
  deontic types), kept to what a checklist can evaluate: conjunctions, exemptions and derived
  conditions.

## Roadmap

- **In the model today**: jurisdictions, acts, provisions, quotes and their English translations, the
  information items each provision names; the normative layer (`Obligation`, `Condition`, `Action`, `ActorRole`);
  court decisions and guidance; relations between provisions; official language versions; privacy,
  consumer, accessibility, platform and AI vocabularies; subdivisions (US states).
- **Next**: versions and expressions (FRBR), so the graph can answer "what did the law say on date X".

## License

[CC BY 4.0](LICENSE). Free for any use, commercial included, with attribution, for example:

> legalgraph ontology by Aimix GmbH (https://aimix.io), licensed under CC BY 4.0.
