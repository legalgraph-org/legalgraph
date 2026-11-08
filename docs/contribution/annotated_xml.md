# Annotated XML

The graph is extracted from one annotated XML file per source. There are two kinds, set by `kind`
in source.yaml.

## Official XML

The portal publishes XML: gesetze-im-internet.de; Formex 4 (EU Official Journal: acts,
consolidated texts, CJEU judgments); legislation.gov.uk (Crown Legislation Markup Language); the
Code of Federal Regulations on govinfo.gov; Akoma Ntoso from Fedlex (Swiss federal law).

The annotated file is a copy of the original with attributes in the `lga:` namespace added inside
existing start tags: no new elements, no reformatting. `verify` removes every `lga:` attribute and
checks the result is byte-identical to the original.

## Authored XML

The portal publishes only HTML or PDF. We write the text in
[schemas/law.xsd](../../schemas/law.xsd), a small schema a lawyer can read: `<section num="§ 18">`,
`<paragraph num="(1)">`, `<list>`, `<item num="1.">`. Each `<section>` names the original it comes
from.

`verify` validates the file against the schema and checks that every paragraph's text, as rendered
(below), occurs word for word in that original:

- **HTML** is compared word for word, with whitespace collapsed.
- **PDF** line breaks, hyphenation and ligatures come from the layout, so the comparison is on
  letters only (Unicode NFKC, without whitespace and hyphens), line by line, since page headers and
  footers can fall between lines. Footnote marks are written `<note num="27"/>` and a page break
  that falls inside a paragraph `<page num="15"/>`; the text is compared on either side.

Transcribe whole sections, not only the paragraphs the graph uses, so the reviewer sees the
provision in context.

## How text is rendered

Quotes and the word check use the same fixed rules:

- whitespace collapses to one space;
- a list item starts a new line with its number (`<DT>1.</DT><DD>…</DD>`,
  `<ITEM><NP><NO.P>(a)</NO.P><TXT>…` or `<item num="1.">`), and a list ends its line;
- a paragraph's number comes first (`num`, `<NO.PARAG>`);
- in Formex, a subparagraph (`<ALINEA>`) starts a new line, and quotation marks (`<QUOT.START>`)
  become the characters their `CODE` names;
- `<BR/>` is a line break;
- footnotes (`<FnR>`, `<NOTE>`) are dropped.
