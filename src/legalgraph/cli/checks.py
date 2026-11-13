"""Live freshness checks against the official portals (needs network)."""

import click

from legalgraph import amendments
from legalgraph.cli.main import cli, load_data
from legalgraph.load import Sources


@cli.group()
def checks() -> None:
    """Live freshness checks against the official portals (needs network)."""


@checks.command("amendments")
@click.argument("ids", nargs=-1)
@click.pass_obj
def checks_amendments(sources: Sources, ids: tuple[str, ...]) -> None:
    """Compare recorded amendments against what the portals show today.

    IDS are act ids (EU-2016-679) or jurisdiction codes (DE, EU, US-CA); empty means all
    acts with a live checker. Fails when a portal shows a newer amendment than the graph.
    """
    results = amendments.run(list(ids), data_graph=load_data(sources))
    failed = [r for r in results if not r.ok]
    for r in results:
        marker = "ok" if r.ok else ("skip" if r.skipped else "FAIL")
        click.echo(f"{marker:4} {r.act:22} {r.message}")
    click.echo(f"{len(results) - len(failed)}/{len(results)} checks pass")
    if failed:
        raise click.ClickException(f"{len(failed)} amendment check(s) failed")
