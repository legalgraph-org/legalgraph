# Language versions, consolidated texts and their proof

EU acts are equally authentic in every official language, and the Publications Office publishes
each language version as Formex 4 XML. Other jurisdictions publish official translations too. An
original's `role` in source.yaml says what it is:

| Role | What it is |
|---|---|
| `text` (default) | The annotated text (for EU law, English). |
| `parallel` | Another language version, kept unannotated. Each provision is read from the same element; `verify` checks it exists there, with the same `IDENTIFIER` and the same number of lines. Its text becomes the quote `<provision>-q1-<lang>`, a `lgo:languageVersionOf` the main quote: no translation needed. |
| `authentic` | The Official Journal publication (Formex from 2004, PDF before), when the annotated text is a consolidated version. |
| `amendment` | An amending act, with `amends:` listing the places it changes that the graph quotes (`Art. 5(3)`, `Art. 11a`). |
| `corrigendum` | A correction published in the Official Journal, with `corrects:` listing the places it changes (`Art. 37(1)`, `Recital 71`, `Annex I(23b)`, or `Whole text` for a correction made throughout), copied from the corrigendum. |

## Consolidated texts

The Publications Office's consolidated versions work amendments and corrigenda in, but they are a
documentation tool, not the law. So when a source holds an `authentic` text, `verify` proves every
line (subparagraph, point) of every quoted provision, in every language. Each line either:

- reads exactly as in the authentic text, or
- has its place listed by a corrigendum or amending act of the same language.

A line an amending act changed must occur word for word in that act. Quotation marks are compared
as one character: quoted in an amending act, ‘…’ becomes “…”. A line that differs only in its final
punctuation (a last point that became a middle one when a point was added after it) counts as
unchanged. The authentic text may be Formex, HTML or PDF. Dashes and footnote marks set directly
after a word are typesetting and are not compared.

This is how, for example, the 2018 corrigendum of Art. 37(1) GDPR is accounted for, and how
Art. 5(3) of the ePrivacy Directive, as replaced in 2009, is traced to Directive 2009/136/EC.

Consolidated texts leave the recitals out. Recitals come from the Official Journal text, in a second
source (the GDPR's are in `eu/gdpr-recitals`).

## Corrigenda of an annotated Official Journal text

When the annotated text is the Official Journal text itself, `verify` fails if a corrigendum
corrects a quoted provision. Apply the corrigendum first.

## Parallel versions of authored texts

A portal that publishes no XML may still publish an official translation as HTML or PDF (the
Ukrainian parliament's English on zakon.rada.gov.ua, the CNIL's English versions of its decisions).
It becomes a `parallel` original whose `annotated` names a second file written in
[schemas/law.xsd](../../schemas/law.xsd) in that language.

- Only `lga:provision` and `lga:url` annotate its provisions.
- Each is matched to the annotated text by `lga:provision`, not by position. A provision the
  translation lacks simply gets no official version.
- `verify` checks its words against its own original, and each translated provision's line count
  against the text's.
- `as_of` is the translation's date. `verify` fails when an amendment note in the original, inside
  or directly after a translated provision, is newer than that: an official translation older than
  the text must not stand as its English. Keep such notes out of the word check with `text_ignore`.

## Downloading from Cellar

Cellar serves each language version as a zip for a CELEX number
(`https://publications.europa.eu/resource/celex/32016R0679`, or `02016R0679-20160504` for a
consolidated version), with the headers `Accept: application/zip;mtype=fmx4` and
`Accept-Language: eng`. Use `fetch: zip-member`: the zip is rebuilt on every request, the XML
inside it is not.
