# legalgraph

An open knowledge graph of the laws that tell businesses what they must disclose and do online: the legal notice (*Impressum*, *mentions légales*), privacy and consent, selling to consumers, accessibility, platforms and AI. It covers the EU and most of Europe, the UK, Ukraine, the US and California.

Every provision is quoted from the official text, kept byte for byte in this repo, with an English translation where the original is in another language. Rules turn provisions into what a business must do, and a checklist shows which rules apply to a given business.

**Browse it on [legalgraph.org](https://legalgraph.org).**

> Researchers, not lawyers. Nothing here is legal advice. Check the official text before relying on an entry, and ask a lawyer admitted in your country for decisions that matter.

## What is in it

- 40+ countries, plus the EU and the EEA
- 100+ legal acts, 500+ provisions, 600+ verbatim quotes
- 20+ court and authority decisions, with their outcomes (fines, damages, injunctions)
- 150+ rules, each traced to the provisions it comes from

`make stats` prints the current counts.

The graph is [Turtle](https://www.w3.org/TR/turtle/) following the [legalgraph ontology](ontology/). If RDF, Turtle or SPARQL are new to you, see the [method](https://legalgraph.org/en/method) and the [glossary](https://legalgraph.org/en/glossary).

## Try it locally

You need [uv](https://docs.astral.sh/uv/). [bun](https://bun.sh) is needed for the website, [Docker](https://www.docker.com) for the SPARQL server.

```sh
git clone https://github.com/legalgraph-org/legalgraph.git
cd legalgraph
make install     # Python environment and the legalgraph command
make check       # verify law texts, validate the graph, lint, test
```

Then:

```sh
make export                                   # dist/legalgraph.{ttl,nt,jsonld}
uv run legalgraph query register-entry        # run a query from queries/
uv run legalgraph checklist -e DE -f CommercialDigitalService   # rules for a business
make sparql      # SPARQL editor on http://localhost:3030 (Docker)
make serve       # the website on http://localhost:4321 (bun)
```

`make help` lists every target.

## Use the data

- **Download** the whole graph in Turtle, N-Triples or JSON-LD from [legalgraph.org/en/download](https://legalgraph.org/en/download).
- **Query** it with SPARQL: `make sparql` loads it into Apache Jena Fuseki ([docs/sparql-with-fuseki.md](docs/sparql-with-fuseki.md)).
- **Fetch** a single resource: `https://legalgraph.org/id/<identifier>` with `Accept: text/turtle`.
- **AI agents** can look up which rules apply, quote the provision behind each and link to it, instead of answering from memory.

## Repository layout

| Path | What it holds |
|---|---|
| [sources/](sources) | Official law texts, byte for byte, with annotated copies ([how to add one](docs/contribution/add_new_source.md)) |
| [data/](data) | The graph: generated Turtle, hand-curated acts, rules, cases, translations |
| [ontology/](ontology) | The model: classes, properties, vocabularies, SHACL shapes ([guide](ontology/README.md)) |
| [queries/](queries) | Example SPARQL queries |
| [scenarios/](scenarios) | Example businesses and the rules each must get |
| [src/legalgraph/](src/legalgraph) | The `legalgraph` command |
| [site/](site) | The website |
| [docs/](docs) | [How it works](docs/how-it-works.md), [translations](docs/translations.md), [the website](docs/website.md), [SPARQL](docs/sparql-with-fuseki.md), [contributor guides](docs/contribution/README.md) |


## Contribute

More laws, more countries, more court decisions, better English: all welcome.

- **Something wrong or missing?** Open an [issue](https://github.com/legalgraph-org/legalgraph/issues) with a link to the official text.
- **A question?** Open an issue too.
- **A change?** Open a pull request; `make check` must pass. For anything bigger than a fix, open an issue first. The guide is [CONTRIBUTING.md](CONTRIBUTING.md).
- Careful, long-term contributors can become [maintainers](MAINTAINERS.md).

## License

- Data, annotations and queries: [CC BY 4.0](LICENSE-DATA). Attribution, for example: *legalgraph by Aimix GmbH (https://aimix.io), licensed under CC BY 4.0.*
- Code: [MIT](LICENSE).
- The law texts are official works, redistributed unchanged and not covered by either licence.

