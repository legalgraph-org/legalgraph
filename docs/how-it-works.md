# How the graph works

How law texts become Turtle, what a rule is, how the graph is validated, and how its identifiers
look. The website's [method](https://legalgraph.org/en/method) page walks through the same steps
with one duty as the example.

## From law text to graph

A legal professional reviewing the graph should start from the law, not from Turtle. The ETL:

1. **Fetch.** Every law text is downloaded by `legalgraph sources fetch` as its `source.yaml` index
   describes (a file from the portal's zip, an HTML fragment, or a PDF) and committed with its
   SHA-256. `legalgraph sources fetch --check` downloads again and fails if a portal's text has
   changed; run on a schedule, it proves the committed texts are authentic and have not drifted.
2. **Annotate.** One XML per act carries the annotations (`lga:` attributes) on the exact provisions
   and items the graph uses. Where the portal publishes XML, it is the official file plus
   annotations, proven byte-identical once they are removed. Where it publishes only HTML or PDF,
   we write the text in [schemas/law.xsd](../schemas/law.xsd), checked word for word against the
   downloaded original.
3. **Extract.** `legalgraph sources extract` generates `data/extracted/<id>.ttl` mechanically. Every
   provision and quote records the original file (`lgo:sourceDocument`) and the element in the
   annotated XML (`lgo:sourceElement`) it came from.

```
gesetze-im-internet.de/ddg/xml.zip
  └─ sources/de/ddg/BJNR0950B0024.xml            the official file, byte for byte
       └─ BJNR0950B0024.annotated.xml            + lga: attributes (proven: nothing else differs)
            └─ data/extracted/de/ddg.ttl         generated, never hand-edited
```

The official formats read today: gesetze-im-internet.de XML (German federal law), Formex 4 (the EU
Official Journal: acts, consolidated texts, judgments), legislation.gov.uk XML (UK), the Code of
Federal Regulations XML (US), Akoma Ntoso (Swiss federal law on Fedlex), and, where only HTML or PDF
exists, our own schema checked word for word against the original.

For EU law the graph quotes the consolidated text (the act with its amendments and corrigenda
worked in), and proves it against the authentic texts: every line of a quoted provision reads as in
the Official Journal, or occurs word for word in an amending act or corrigendum that lists its
place. Countries not yet built from their law texts are curated by hand in
[data/acts/](../data/acts) and move to `sources/` one by one. [Add a new source](contribution/add_new_source.md)
has the details; the [sources page](https://legalgraph.org/en/sources) lists the current coverage.

## Review status

Every act, provision, rule and translation carries one:

- **Source checked**: citation and quotes compared word for word with the text at the source URL.
  This is a check of the wording, not a legal review.
- **Reviewed**: a translation a person has read against the original.
- **Draft**: from research notes or a machine, not yet checked. Draft acts have no quotes. Do not
  rely on them.

Quotes may skip parts of a provision; omissions are marked `[…]`. Where a quote comes from a
translation that is not legally binding (Swiss federal law in English, Latvian law in English), it
has `lgo:officialLanguageVersion false`.

## Rules and the checklist

Provisions say what the law is; rules say what that means for a business. Each rule
([data/rules/](../data/rules), `lgo:Obligation`) names who it addresses, the conditions under which
it applies (`lgo:appliesWhen`, all must hold) and its exemptions (`lgo:unless`), the information to
disclose and the actions to take, and the provisions it is read from.

Conditions are facts about a business ("sells to consumers online", "sets non-essential cookies"),
each with a yes/no question and the provision whose words define it; some follow from others. Where
the business is established, and where it offers its services, are answered once as a jurisdiction:
"established in Austria" makes "established in the EU" and "in the EEA" hold (`lgo:establishedIn`,
`lgo:offersIn`). A rule resting on a directive names the national provision of the country of
establishment (found through `lgo:implements`), and a national rule that spells it out
(`lgo:refines`, § 5 DDG for Article 5 of the e-Commerce Directive) takes its place.

Rules are our interpretation: they are **Draft** until a lawyer reviews them.

```sh
uv run legalgraph checklist --questions                          # every condition and its question
uv run legalgraph checklist -e AT -f CommercialDigitalService -f HasVatId
uv run legalgraph checklist -e US -m EU -f ProcessesPersonalData
uv run legalgraph checklist --scenario scenarios/de-gmbh-shop.yaml
```

The [scenarios](../scenarios) are example businesses with the rules they must get; the tests check
the rules against them. The website's checklist evaluates the same rules in the browser.

## Validation

`legalgraph validate` (part of `make check`) checks:

1. Turtle syntax, file by file.
2. Every `lgo:` / `lgv:` term is defined in the ontology, and every `lg:` resource that is
   referenced is defined somewhere in the data.
3. The ontology's SHACL shapes (for example: an act has one jurisdiction and a source URL; a
   provision marked *Source checked* has at least one quote; an obligation names the provisions it
   comes from).
4. Every non-English text has a current English translation (see [translations.md](translations.md)),
   unless it is an official language version of an English text (EU law).

## Identifiers

| Prefix | Namespace | Used for |
|---|---|---|
| `lgo:` | `https://legalgraph.org/ontology#` | Ontology classes and properties |
| `lgv:` | `https://legalgraph.org/vocab/` | Controlled vocabularies (SKOS) |
| `lg:` | `https://legalgraph.org/id/` | Resources in this graph |
| `eli:` | `http://data.europa.eu/eli/ontology#` | European Legislation Identifier ontology |

Resource names follow `<ISO>-<act>[-<provision>][-q<n>]`, e.g. `lg:DE-DDG-s5-1-q1`:

```turtle
lg:DE-DDG-s5-1 a lgo:Provision ;
    eli:is_part_of lg:DE-DDG ;
    lgo:citation "§ 5 Abs. 1 DDG" ;
    lgo:implements lg:EU-2000-31-art5-1 ;
    lgo:regulates lgv:ProviderIdentification ;
    lgo:requiresDisclosureOf lgv:ProviderName , lgv:GeographicAddress , lgv:EmailAddress , … ;
    lgo:reviewStatus lgv:SourceChecked .

lg:DE-DDG-s5-1-q1 a lgo:Quote ;
    lgo:quoteOf lg:DE-DDG-s5-1 ;
    lgo:text """(1) Diensteanbieter haben für geschäftsmäßige, in der Regel gegen Entgelt angebotene
digitale Dienste folgende Informationen […] ständig verfügbar zu halten: …"""@de ;
    lgo:sourceUrl "https://www.gesetze-im-internet.de/ddg/__5.html"^^xsd:anyURI .
```

## Citing the graph

Articles that rely on the graph link to identifiers such as `/id/DE-DDG-s5-1`. To keep a claim and
its evidence together, `generate-site` publishes:

- `downloads/citations.json`: every identifier with a SHA-256 of its triples and the graph version,
  so a site's build can check that every cited identifier exists, and see when what it says changed;
- `downloads/rules.json`: the rules, conditions and scenarios, so a checklist in an article is
  generated from the graph rather than retyped;
- schema.org `Legislation` markup (ELI-aligned JSON-LD) on every act and provision page.
