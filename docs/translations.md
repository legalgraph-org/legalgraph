# Translations

The graph is always complete in English: `legalgraph validate` (and so `make check`) fails while any
non-English text lacks English.

- A **quote** in another language gets an `lgo:Translation` node in
  `data/translations/en/<jurisdiction>.ttl`. It records how it was made (machine, human or official
  translation), by whom or by which model, when, and a SHA-256 of the source text. If the quote
  changes, the hash stops matching and the translation is reported as stale.
- A **title, label or comment** in another language needs an `@en` literal on the same resource.
  Which properties need one is declared in the ontology (`lgo:englishRequired`).

EU texts are quoted in English and German, both official, so they need no translation.

Translations are produced by a machine and reviewed by people:

```sh
uv run legalgraph translations check                      # what is missing or stale
uv run legalgraph translations export -o worklist.json    # JSON worklist for a translator
# … a translator (a language model, or a person) fills in each item's "translation" …
uv run legalgraph translations apply worklist.json --translated-by <model-or-name> [--method human]
```

`apply` writes new translations with review status *Draft*. To review one, correct the English in
the translation file if needed, add `lgo:reviewedBy "Your Name"` and set
`lgo:reviewStatus lgv:Reviewed`. A translation is a reading aid: the source-language quote is what
the law says.
