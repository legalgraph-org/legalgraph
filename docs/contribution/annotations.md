# Annotations

Annotations are attributes in the namespace `https://legalgraph.org/ns/annotation#` (prefix `lga`),
added to the [annotated XML](annotated_xml.md). Values are identifiers from the graph (`lg:` without
the prefix) or concepts from the ontology's vocabularies (`lgv:` without the prefix, see
[ontology/src/vocab/](../../ontology/src/vocab)); several values are separated by spaces. Any other
`lga:` attribute is rejected.

This is where interpretation happens, so it sits on the exact words that justify it.

## On the root element: the document

| Attribute | Meaning | Example |
|---|---|---|
| `lga:act` | Identifier of the document | `DE-DDG` |
| `lga:jurisdiction` | Jurisdiction it comes from | `DE` |
| `lga:act-type` | Concept from `vocab/act-types.ttl` | `Statute`, `Ordinance`, `Judgment`, `AuthorityDecision`, `Guidelines` |
| `lga:url` | Human-readable page of the document | `https://www.gesetze-im-internet.de/ddg/` |
| `lga:transposes` | EU acts it transposes (optional) | `EU-2000-31` |

Title, short name and date come from the document itself: `langue`, `amtabk`/`jurabk` and
`ausfertigung-datum` on gesetze-im-internet.de, `<meta>` in authored XML.

`lga:act-type` decides what kind of document it is: `Judgment` makes a `lgo:CourtDecision` (with
its ECLI from the document, where it has one), `AuthorityDecision` a `lgo:AuthorityDecision`,
`Guidelines` a `lgo:Guidance`, anything else a `lgo:LegalAct`.

## On a provision: one paragraph

A provision is a `<P>` or `<paragraph>` (one Absatz), or a numbered item such as each definition of
Art. 4 GDPR.

| Attribute | Meaning | Example |
|---|---|---|
| `lga:provision` | Identifier | `DE-DDG-s5-1` |
| `lga:citation` | How it is cited | `§ 5 Abs. 1 DDG` |
| `lga:url` | Page of the provision (optional; else the original's `page`, else the document's `lga:url`) | `https://www.gesetze-im-internet.de/ddg/__5.html` |
| `lga:regulates` | Disclosure types it creates duties for, or legal concepts it sets conditions for | `ProviderIdentification`, `Consent` (Art. 7 GDPR) |
| `lga:enforces` | Disclosure types it is a basis for enforcing | `ProviderIdentification` (§ 3a UWG) |
| `lga:defines` | Information items or legal concepts it establishes | `VatId` (§ 27a UStG), `Consent` (Art. 4(11) GDPR) |
| `lga:authorises` | Acts issued under it | `DE-DLInfoV` (§ 6c GewO) |
| `lga:implements` | EU provisions it implements (optional) | `EU-2000-31-art5-1` |
| `lga:requires` | Information items it names, when it has no numbered items | `ResponsibleEditor` |
| `lga:explains` | Concepts a recital explains (not binding) | `PersonalData` (Recital 30 GDPR) |
| `lga:interprets` | Provisions a ruling or guidance interprets | `EU-2002-58-art5-3` (Planet49) |
| `lga:specifies` | Provisions of another act it fills in under an opening clause | `EU-2016-679-art37-1` (§ 38 BDSG) |
| `lga:takes-precedence-over` | Provisions it overrides where both apply (lex specialis) | `EU-2016-679-art6-1` (§ 25 TDDDG) |
| `lga:refers-to` | Provisions of another act its text points to | `EU-2016-679-art4-11` |
| `lga:applies` | Provisions a decision applies to the facts of its case | `DE-TDDDG-s25-1` (OLG Köln, Tenor 1) |
| `lga:penalises` | Provisions whose breach a penalty provision makes an offence or fines | `DE-TDDDG-s25-1` (§ 28 Abs. 2 TDDDG) |

A provision needs at least one of `regulates`, `enforces`, `defines`, `authorises`, `explains`,
`interprets`, `specifies`, `applies` or `penalises`. Each provision becomes one quote
(`<provision>-q1`) holding its full text. References within an EU act ("point (f) of Article 6(1)",
"paragraph 1") are read from the English text mechanically and become `lgo:refersTo` to the act's
provisions in the graph.

If no concept in the vocabularies fits, add one in the same pull request, with a definition that
states the law, not an opinion.

## On a numbered item inside a provision

A `<DD>` or `<item>`:

| Attribute | Meaning | Example |
|---|---|---|
| `lga:requires` | Information items this item names | `VatId EconomicIdNumber` |
| `lga:defines` | Concepts this item defines | `LawfulBasisConsent` (Art. 6(1)(a) GDPR) |

The provision's `lgo:requiresDisclosureOf` is the union of its own and its items' `lga:requires`,
and likewise `lgo:defines`.
