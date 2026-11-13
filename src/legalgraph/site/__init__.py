"""Data for the browsable site in site/ (Astro).

Python owns the meaning, Astro the presentation. This module reads the graph and writes:

- site/src/data/*.json: one JSON file per collection (jurisdictions, acts, provisions, concepts,
  documents) plus the graph for the interactive view and summary numbers. Astro loads them as
  content collections and validates them with Zod schemas (site/src/content.config.ts).
- site/public/id/<name>.ttl, site/public/vocab/<name>.ttl: the triples about each resource, so
  every identifier can also be served as Turtle (see site/worker/ for content negotiation).
- site/public/downloads/: the whole graph as Turtle, N-Triples and JSON-LD, and the ontology.
- site/public/sources/: the law texts and their indexes, so a reader can check them in the browser.

Output is deterministic: the same graph gives the same files.
"""

from legalgraph.site.build import DATA_DIR, PUBLIC_DIR, SITE_DIR, SiteError, bun, generate_data
from legalgraph.site.legislation import last_amended

__all__ = ["DATA_DIR", "PUBLIC_DIR", "SITE_DIR", "SiteError", "bun", "generate_data", "last_amended"]
