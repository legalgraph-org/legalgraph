.PHONY: help install sources validate test lint check stats quotes export translations upstream site serve site-check i18n-extract i18n-check export-full sparql

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install: ## Install the CLI and dev tools into .venv
	uv sync

sources: ## Verify annotated law texts against the originals; check generated Turtle is current
	uv run legalgraph sources verify
	uv run legalgraph sources extract --check

validate: ## Turtle syntax, undefined terms, SHACL shapes, English translations
	uv run legalgraph validate

test: ## Run the test suite
	uv run pytest

lint: ## Ruff lint and format check
	uv run ruff check src tests
	uv run ruff format --check src tests

check: sources validate lint test ## Everything a pull request must pass

stats: ## Count resources by class
	uv run legalgraph stats

quotes: ## Print key quotes (COUNTRY=DE to filter)
	uv run legalgraph quotes $(if $(COUNTRY),--country $(COUNTRY))

export: ## Write dist/legalgraph.{ttl,nt,jsonld}
	uv run legalgraph export --format ttl -o dist/legalgraph.ttl
	uv run legalgraph export --format nt -o dist/legalgraph.nt
	uv run legalgraph export --format jsonld -o dist/legalgraph.jsonld

export-full: ## Write dist/legalgraph-with-ontology.ttl (the data with the ontology and vocabularies)
	uv run legalgraph export --format ttl --with-ontology -o dist/legalgraph-with-ontology.ttl

sparql: export-full ## Query the graph in Apache Jena Fuseki on http://localhost:3030 (needs Docker)
	docker compose up

translations: ## Report text that lacks a current English translation
	uv run legalgraph translations check

upstream: ## Has any official text changed on its portal? (network)
	uv run legalgraph sources fetch --check

amendments: ## Do portals show newer amendments than the graph records? (network)
	uv run legalgraph checks amendments $(if $(ACTS),$(ACTS),)

site: i18n-check ## Build the browsable site into site/dist (needs bun)
	uv run legalgraph generate-site

site-check: i18n-check ## Site: translations, unit tests (vitest), type check (astro check)
	cd site && bun run test && bun run check

i18n-extract: ## Site: src/ -> locales/messages.pot -> msgmerge into locales/<locale>.po (needs GNU gettext)
	cd site && bun run i18n:extract

i18n-check: ## Site: every message translated, not fuzzy, same placeholders and tags
	cd site && bun run i18n:check

serve: ## Browse the graph locally on http://localhost:4321 (needs bun)
	uv run legalgraph serve-site
