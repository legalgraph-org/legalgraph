# The website

[site/](../site) is an [Astro](https://astro.build) site that makes the graph browsable: a page for
every country, act, provision, quote, translation, source document and vocabulary term, a
comparison matrix (which information item each country's law requires), a checklist, and an
interactive graph (Cytoscape.js). Quotes are shown next to their English translation, line by line.

Each law text has a reading page (`/id/<act>-source`): the annotated sections of the official text,
paragraph by paragraph, with the provisions in the graph highlighted and paired with their English,
the information items each line names as labels on that line, and the annotated XML of the section.

## Run and build

Requires [bun](https://bun.sh).

```sh
make serve       # http://localhost:4321, reloads on changes to site/ (rerun after data changes)
make site        # data + Astro build into site/dist
make site-check  # translations, unit tests, type check
```

Python writes the data (`site/src/data/*.json`, one Turtle file per resource in `site/public/id/`
and `site/public/vocab/`, downloads, and copies of the law texts); Astro loads it as content
collections with Zod schemas, so a mismatch fails the build. Generated files are not committed.

## The site's languages

The site's own prose (home, about, articles, legal pages, navigation) is in English and German, under
`/en/…` and `/de/…`. The old unprefixed addresses redirect to `/en`. What comes from the graph
(names, citations, quotes, rules) stays in its original language, at one unprefixed address
(`/id/…`, `/vocab/…`, `/checklist`).

Translation uses gettext: pages call `t("English text")`, and `make i18n-extract` collects the
messages into `site/locales/messages.pot` and merges them into `site/locales/de.po` (needs GNU
gettext: `brew install gettext`). `make i18n-check` fails on any missing or fuzzy translation, and
`make site` runs it first. Articles and legal pages are Markdown per language (`name.md`,
`name.de.md`).

## Deploying to Cloudflare Pages

`site/dist` is a static site; `site/functions/` adds content negotiation, so `/id/DE-DDG` returns
the HTML page to browsers and Turtle to clients sending `Accept: text/turtle`. From CI, after
`make check`:

```sh
uv run legalgraph generate-site
cd site && SITE_URL=https://legalgraph.org bunx wrangler pages deploy dist --project-name <project>
```

Run `wrangler` from `site/` so it picks up `functions/`. The identifiers live on legalgraph.org
(`https://legalgraph.org/id/DE-DDG`), so the site must be served from that domain's root for each
identifier to resolve to its page.

## Search engines

The build writes `/sitemap.xml` (an index of `/sitemap-0.xml`, `-1` …; every page, with its English
and German versions linked as alternates) and a `/robots.txt` naming it. For Google Search Console,
add legalgraph.org as a *domain* property, verify it with the TXT record Google gives you, and
submit `https://legalgraph.org/sitemap.xml`. Nothing is added to the pages, and visitors are not
tracked.
