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

"Short passages reproduced with the source indicated" is not a basis: the repository keeps the
whole original, not a quotation of it.

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

## Guidance we may read but not republish

A regulator's guide is often worth more to the graph than a news item: it says how the authority
reads the law, point by point. When no licence above lets us keep it, the graph keeps **what it
concludes**, in our own words, and links the original for readers to check:

```yaml
- id: es-aepd-guia-cookies
  title: "Guía sobre el uso de las cookies"
  publisher: "Agencia Española de Protección de Datos (AEPD)"
  url: "https://www.aepd.es/guias/guia-cookies.html"   # the page readers are sent to
  date: 2024-05-01
  why_link_only: "regulator's guide; no legal notice found that allows reproducing it"
  claim: "Guidance, not binding text: how the AEPD applies art. 22.2 LSSI to cookie banners."
  supports: [ES-LSSI-art22-2]                          # the provision it explains
  local_copy:                                          # the version the findings were read from
    url: "https://www.aepd.es/guias/guia-cookies.pdf"
    file: guia-cookies.pdf
    retrieved_on: 2026-11-15
    sha256: f968645392c12d3670221cf459f9765a34bb6e6dc12de3d6d753a2b917687085
  guidance:
    id: ES-AEPD-COOKIES                                # the document in the graph (lgo:Guidance)
    short_name: "AEPD, Guía de cookies"
    title_en: "Guide to the use of cookies (AEPD, May 2024)"
    jurisdiction: ES
    language: es
    findings:                                          # one per point, as provisions of the guide
      - id: ES-AEPD-cookies-s323
        locator: "§ 3.2.3"                             # where the reader finds it
        finding: "Rejecting must be offered at the same time, level and visibility as accepting."
        interprets: [ES-LSSI-art22-2, EU-2002-58-art5-3, EU-2016-679-art7-3]
        regulates: [Consent]
```

- **A finding is never a quote.** State the point in English in your own words, as precisely as
  the original, and no more than it says. Its review status is `Draft`, as for rules.
- **The original stays local.** `uv run legalgraph sources local [ID…]` downloads it into
  `sources/.local/<id>/` (git-ignored), so findings can be checked against it, and reports whether
  the publisher still serves the version that was read (`sha256`; for a web page, the same words).
  When it changed, it is saved next to the copy as `<name>.latest<ext>`: re-read it, update the
  findings, `retrieved_on` and `sha256`. Nothing under `sources/.local/` is committed or published.
- A guide whose licence does allow it (an official act, an open licence) is a source like any other,
  with quotes: see [Add a new source](add_new_source.md).
