# Licences and link-only sources

The repository keeps every original byte for byte, and legalgraph.org republishes the quotes. That is
fine for official works and for texts their publisher licenses for reuse. Anything else is linked,
not copied.

## Licences

Every new source.yaml must say which licence applies (`licence`) and why (`licence_basis`, naming the
provision or legal notice it rests on). `legalgraph sources verify` rejects an unknown licence, or one
without its basis.

| `licence` | For |
|---|---|
| `public-domain` | US federal works (17 U.S.C. § 105); statutes and judicial opinions under the government edicts doctrine |
| `official-work` | laws, decrees and court decisions exempt by national copyright law (§ 5 Abs. 1 UrhG in Germany, § 7 UrhG in Austria, Art. 5 URG in Switzerland); official publications for general information (§ 5 Abs. 2 UrhG) |
| `licence-ouverte-2.0` | French public data (Légifrance, CNIL) |
| `ogl-3.0` | UK Crown copyright (legislation.gov.uk) |
| `reuse-with-attribution` | publishers whose legal notice allows reproduction with the source named (EUR-Lex under Commission Decision 2011/833/EU, the EDPB) |

The value becomes `lgo:licence` on the source document and is shown on its page. Official texts are
redistributed unchanged for reference and are not covered by this repository's own licences.

If a text fits none of these, it is not a source: link it instead.

## Link-only sources

Someone else's writing (news, law-firm articles, enforcement databases, press releases that add
context) is **not** kept in the repository. It goes into `sources/link-only.yaml`:

- the link, and why it is only linked;
- the claim it backs up, and the graph identifiers it supports;
- at most one short verbatim excerpt: 300 characters, with its locator.

```yaml
- id: example-report
  title: "Regulator fines a shop over its cookie banner"
  publisher: "Example News"
  url: "https://example.org/report"
  date: 2022-01-06
  why_link_only: "news report; third-party work"
  claim: "A shop was fined for its cookie banner"
  supports: [DE-OLGK-2024-0119]
  quote: {text: "Refusing must be as easy as accepting.", locator: "para. 2", language: en}
```

`legalgraph sources extract` turns the list into `data/extracted/link-only.ttl`
(`lgo:ExternalReference`), shown as "Further reading" on the pages it supports.

Use a link, too, for an official text the publisher has since withdrawn or anonymised, such as an
archived copy of a decision published before the parties' names were removed. The archive link
makes the fact checkable without the graph republishing what the publisher took down.
