# Contributing to legalgraph

legalgraph is meant to grow: more laws, more countries, more court decisions and authority
decisions, better rules and better English. Corrections are as welcome as new data. This page is
the practical guide; [How to contribute](https://legalgraph.org/en/blog/how-to-contribute) on the
website explains the idea behind it.

Everything happens on GitHub:

- **Issues** for anything you found or want: a wrong citation, a law that changed, a missing
  country, a translation that reads badly, a question about the model. Link the official text
  wherever you can.
- **Pull requests** for changes. For anything bigger than a fix (a new country, a new kind of
  data, a change to the ontology), open an issue first, so we agree on the scope before you
  spend the time.

legalgraph is research, not legal advice, and contributions are held to the same rule: every
statement must trace to the words of an official text, or be marked as a reading.

## Set up

You need [uv](https://docs.astral.sh/uv/) and, for the website, [bun](https://bun.sh).

```sh
git clone https://github.com/legalgraph-org/legalgraph.git
cd legalgraph
make install     # Python environment and the legalgraph command
make check       # what every pull request must pass
make serve       # optional: the website on http://localhost:4321
```

`make help` lists every target.

## The workflow

1. Fork the repository and create a branch.
2. Make the change, following the sections below.
3. Run `make check`. It verifies the law texts against their originals, checks that the generated
   Turtle is current, validates the graph (syntax, undefined terms, SHACL shapes, English for
   every non-English text), lints and runs the tests. If you touched `site/`, run
   `make site-check` too.
4. Open a pull request. Say what you changed, link the official sources, and say how sure you are
   where you interpreted the law.

A maintainer reviews it. For data, the review is mostly a reading of the law: does the quote match
the official text, does the annotation sit on the right paragraph, does the rule follow from the
provisions it names.

## Follow the ontology

The graph has one model, described in [ontology/README.md](ontology/README.md): legal acts,
provisions, quotes, translations, rules (obligations with conditions), court decisions and their
outcomes, and controlled vocabularies (information items, actions, legal concepts, conditions).

- **Use the existing terms.** Before inventing one, search the vocabularies in
  [ontology/vocab/](ontology/vocab): the information item, action or concept you need is
  often there under a more general name.
- **Add a term where one is missing**, in the same pull request: a class in
  `ontology/classes/<ClassName>.ttl` (with the properties whose domain it is; a property without one
  class as its domain goes in `ontology/properties/<name>.ttl`), a concept in the matching vocabulary
  file, with an English label and
  a definition that states the law, not our opinion. `legalgraph validate` rejects any `lgo:` or
  `lgv:` term that is not defined, so the data and the model cannot drift apart.
- **Change the model only with an issue first.** New classes, new properties and new SHACL shapes
  affect every country, so we discuss them before they land.

## What you can add

### A law, or a provision of a law already in the graph

Law texts are never typed in: they are downloaded from the official portal, kept byte for byte,
annotated, and the Turtle is generated from them.
[Add a new source](docs/contribution/add_new_source.md) is the full guide (with
[more guides](docs/contribution/README.md) on annotations, EU language versions and licences); in
short:

1. Create `sources/<country>/<act>/source.yaml`: where the official file comes from, and on what
   terms it may be republished (`licence`, `licence_basis`).
2. `uv run legalgraph sources fetch <id>` downloads it and records its SHA-256 and date.
3. Annotate it: add `lga:` attributes to the official XML, or, where the portal has only HTML or
   PDF, transcribe the sections into [schemas/law.xsd](schemas/law.xsd).
4. `uv run legalgraph sources verify <id>` proves the annotated copy matches the original, and
   `uv run legalgraph sources extract <id>` writes `data/extracted/<id>.ttl`. Never edit that file
   by hand.
5. Register a new act in [data/amendment-checks/coverage.yaml](data/amendment-checks/coverage.yaml)
   (how its portal is checked for amendments, or why it isn't) and record the latest amendment you
   saw in `data/amendment-checks/<country>.ttl`.

Some portals block automated downloads. Texts waiting for someone to save them in a browser are
among the issues labelled [`help wanted`](https://github.com/legalgraph-org/legalgraph/labels/help%20wanted):
a good first contribution. Comment on one before you start, so two people don't save the same text.

### A country

Add the jurisdiction to [data/jurisdictions.ttl](data/jurisdictions.ttl) (ISO code, official
languages, membership of the EU or EEA, what the local legal notice is called), then its laws as
above. Countries whose laws are still curated by hand live in [data/acts/](data/acts); moving one
of them to `sources/` is very welcome.

### A court decision or an authority decision

The decision's text is a source like a law (see the CJEU judgments in `sources/eu/`, and
[Add a court or authority decision](docs/contribution/add_court_or_authority_decision.md)). Its case
number, outcomes (injunction, fine, damages: who, how much, for breach of which provision) and the
rules it illustrates go into `data/cases/<country>.ttl`. Every outcome names the point of the
decision that states it (`lgo:statedIn`), so it can be checked against the quoted words.

News reports and law-firm articles are other people's work: they are linked, not copied, through
`sources/link-only.yaml` (see [Licences and link-only sources](docs/contribution/licences_and_link_only.md)).

### A rule

Rules ([data/rules/](data/rules)) say what provisions mean for a business: who must do what, under
which conditions, and which provisions it comes from. They are our reading of the law and stay
**Draft** until a lawyer reviews them. If you change one, update or add an example business in
[scenarios/](scenarios): the tests check that each one gets exactly its rules.

### English translations

Every non-English quote needs English. `uv run legalgraph translations check` lists what is missing
or stale; [docs/translations.md](docs/translations.md) explains how translations
are produced and reviewed. Reviewing a machine translation against the original is one of the most
useful things a native speaker can do.

### The website and the code

The website is in [site/](site) (Astro), the command-line tool in [src/legalgraph/](src/legalgraph)
(Python). Its own pages are in English and German; see
[docs/website.md](docs/website.md).

## Review status

Every act, provision, rule and translation carries one:

- **Draft**: from research notes or a machine, not yet checked. Fine to contribute; not to be
  relied on.
- **Source checked**: citation and quotes compared word for word with the official text.
- **Reviewed**: a translation that a person has read against the original.

Moving an entry from Draft to Source checked is a contribution in itself: add the quote from the
official source, set the status, and `make check` must pass.

## Licence of contributions

By contributing, you agree that your contribution is published under the licence of the part you
contribute to: [CC BY 4.0](LICENSE-DATA) for data, annotations and queries, [MIT](LICENSE) for
code. Official law texts are not covered by either; they are redistributed as published.

## Maintainers

Maintainers review and merge pull requests. Contributors who have made substantial, careful
contributions over time can be invited to join them; see [MAINTAINERS.md](MAINTAINERS.md).
