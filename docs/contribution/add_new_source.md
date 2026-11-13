# Add a new source

The graph is built from the law as published, not typed in by hand. A reviewer starts with the text
exactly as the official portal serves it, and can follow every step to the Turtle.

```
portal ──fetch──► original (committed, SHA-256 in source.yaml)
                     │
                     ├─ official XML:  annotated copy = original + lga: attributes   (verify: byte-identical)
                     └─ HTML or PDF:   authored XML in schemas/law.xsd + lga: attributes (verify: same words)
                                          │
                                          └──extract──► data/extracted/<id>.ttl  (verify: up to date)
```

A source is a law, a court decision, an authority decision or a regulator's guidance. Everything
here applies to all of them; [Add a court or authority decision](add_court_or_authority_decision.md)
covers what a decision needs on top.

## Steps

1. Create `sources/<country>/<act>/source.yaml` (below), with `sha256` set to a distinct
   placeholder for each original (`pending-1`, `pending-2`, …).
2. `uv run legalgraph sources fetch <id>` downloads the originals and fills in `sha256` and
   `retrieved_on`.
3. Write the annotated XML: copy the official XML and add `lga:` attributes, or transcribe the
   sections in [schemas/law.xsd](../../schemas/law.xsd). See [Annotated XML](annotated_xml.md) and
   [Annotations](annotations.md).
4. `uv run legalgraph sources verify <id>` proves the annotated copy matches the original;
   `uv run legalgraph sources extract <id>` writes `data/extracted/<id>.ttl`. Never edit that file
   by hand.
5. A new act gets a line in [data/amendment-checks/coverage.yaml](../../data/amendment-checks/coverage.yaml):
   `{kind: <checker>, arg: <portal id>}` when its portal can be checked for newer amendments, or
   `{exempt: "<why not>"}`. Record the latest amendment you saw as an `lgo:AmendmentCheck` in
   `data/amendment-checks/<country>.ttl` (copy a neighbour). `make check` fails for an act missing
   from `coverage.yaml`.
6. `make check`. It also lists the new quotes that need an English translation
   ([translations](../translations.md)).

## One directory per source

`sources/<country>/<act>/`, for example `de/ddg/`:

| File | What it is |
|---|---|
| `source.yaml` | The index: where each original comes from, how it is fetched, when, and its SHA-256. |
| the original(s) | Exactly what `fetch` produces. Never edited by hand. |
| the annotated XML | What the graph is extracted from: the official XML with annotations added, or XML written by us. |

## source.yaml

```yaml
id: de/mstv                      # also the name of data/extracted/<id>.ttl
title: Medienstaatsvertrag
jurisdiction: DE
language: de                     # language of the text (BCP 47)
publisher: Bayerische Staatskanzlei, gesetze-bayern.de (BAYERN.RECHT)
kind: authored-xml               # official-xml | authored-xml
licence: official-work           # on what terms the original may be kept and republished
licence_basis: "§ 5 Abs. 1 UrhG: laws, ordinances and official decrees are official works without copyright"
originals:
  - file: MStV-18.fragment.html
    url: https://www.gesetze-bayern.de/Content/Document/MStV-18
    fetch: html-fragment         # zip-member | html-fragment | rendered | file
    selector: div.cont           # html-fragment: CSS selector of the element holding the law text
    text_ignore: ["sup.satznr"]  # html-fragment: elements left out when comparing words (here: sentence numbers)
    media_type: text/html
    retrieved_on: 2026-10-31     # keep directly above sha256; `fetch` updates both
    sha256: 16ca4084…
annotated: MStV.law.xml
```

Every new source must set `licence` and `licence_basis`: see [Licences and link-only sources](licences_and_link_only.md).

Optional fields of an original:

- `headers`: sent with the download, for example `Accept` for content negotiation.
- `page`: the human-readable page of that text, used as the quotes' source URL.
- `role` and `language`: for language versions, consolidated texts and their proof
  ([EU law](eu_law_language_versions.md)).
- `notes`: shown with the document, for example "consolidated text, a documentation tool".
- `authentic: false`: a text that is a translation published for information (a CJEU judgment
  outside the language of the case).
- `official: false`: a copy from a mirror rather than the official publication (below).
- `wait`: for `fetch: rendered`, the element to wait for before the fragment is cut.

A source may set `document:` to name its source document when `<act>-source` is already taken (the
GDPR's recitals come from a second source).

## Fetch methods

- **`zip-member`**: download a zip and take `member` from it, byte for byte (gesetze-im-internet.de
  publishes every federal law as `https://www.gesetze-im-internet.de/<abbr>/xml.zip`).
- **`html-fragment`**: download a page and keep the element matching `selector`, as BeautifulSoup
  (`html.parser`) serialises it. Portal pages differ on every request (session tokens, timestamps);
  the fragment with the law text does not.
- **`file`**: the response as served, byte for byte (PDF and anything else).
- **`rendered`**: for portals that build the law text with JavaScript (single-page apps such as the
  Czech e-Sbírka): the page is rendered in headless Chromium (`tools/render`, bun and Playwright; run
  `make render-install` once on your machine), then the element matching `selector` is kept as for
  `html-fragment`. Set `wait` to the element that holds the text once rendered, and `text_ignore` to
  hidden duplicates (e-Sbírka renders each defined term twice, once hidden for its tooltip). A render's
  markup changes from one run to the next, its words do not: `fetch --check` compares the words.
  Not for portals behind a bot challenge: those are saved by hand (below), never worked around.

### Mirrors, and checking them against the official text

Sourcing and checking are separate steps. A text may be taken from the official publication, or from
a mirror that is easier to read; a mirror's original says `official: false`. Add the official
publication as a second original with `role: authentic` (downloaded, or `rendered` where the portal
needs it), and `sources verify` checks every annotated line word for word against it as well. The
graph records the outcome on each source document (`lgo:authenticity`): `Official` for an official
text, `VerifiedAgainstOfficial` (with `lgo:verifiedAgainst` naming the official document) for a mirror
checked that way, `NotVerified` for a mirror not checked yet. Example: `sources/cz/oz/` (the
zakonyprolidi.cz mirror, checked against e-Sbírka).

### Portals that block downloads

Some portals block scripts or foreign traffic, or only work in a browser. Open the URL from
source.yaml in a browser, save the page as "Web page, complete", and run
`uv run legalgraph sources fetch <id> --saved <file>`. The parser picks the law text out of it, and
the page is matched to its original by the browser's `<!-- saved from url=(...) -->` marker (a file
downloaded another way needs that line added by hand). Markup that differs without changing the
words (a saved page, rewritten asset links) does not count as a changed original, in `fetch` or
`fetch --check`.

Texts waiting for someone to save them are among the GitHub issues labelled
[`help wanted`](https://github.com/legalgraph-org/legalgraph/labels/help%20wanted): a good first
contribution.

## Commands

```sh
uv run legalgraph sources fetch [ID…]          # download originals; changed ones are written and source.yaml updated
uv run legalgraph sources fetch --check [ID…]  # download and compare only; fails if a portal changed (for CI)
uv run legalgraph sources verify [ID…]         # hashes, byte identity / schema and word check, annotation names
uv run legalgraph sources extract [--check]    # write (or check) data/extracted/<id>.ttl
uv run legalgraph sources reannotate [ID…]     # carry lga: attributes onto a re-fetched official XML
uv run legalgraph checks amendments [ID…]      # do the portals show newer amendments than the graph records?
```

`make check` runs `verify` and `extract --check` (offline). `make upstream` runs `fetch --check` and
`make amendments` runs `checks amendments` (both network); run on a schedule, they prove the
committed texts still match the portals and that no newer amendment has been missed. A portal that
cannot be reached is reported as `skip`, not as a failure.

## When a law changes

`make upstream` or `make amendments` reports it. Run `uv run legalgraph sources fetch <id>` to take
the new text, carry the annotations over (official XML: `uv run legalgraph sources reannotate <id>`,
which leaves any element whose text changed unannotated and names it) or update the transcription
(authored XML), update the act's `lgo:AmendmentCheck`, and run `make check`. `verify` confirms the annotated XML matches the new original, the diff of
`data/extracted/` shows exactly what changed in the graph, and quotes whose text changed are listed
as needing a new English translation.
