"""Command line: legalgraph validate | stats | quotes | checklist | query | export | translations | sources | site |
po-files."""

from legalgraph.cli import checklist, checks, graph, hygiene, site, sources, translations  # noqa: F401 (register the commands)
from legalgraph.cli.graph import QUERIES_DIR, run_query
from legalgraph.cli.main import cli
from legalgraph.po.cli import po_files

# Splitting, merging and filling the site's gettext catalogs (site/locales/*.po) for translation.
cli.add_command(po_files)

__all__ = ["QUERIES_DIR", "cli", "run_query"]
