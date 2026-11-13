"""English translations: check, export a worklist, apply a filled-in worklist."""

from datetime import date
from pathlib import Path

import click

from legalgraph import localisation
from legalgraph.cli.main import cli, load_graphs
from legalgraph.load import Sources


@cli.group()
def translations() -> None:
    """English translations: check, export a worklist, apply a filled-in worklist."""


@translations.command("check")
@click.pass_obj
def translations_check(sources: Sources) -> None:
    """List text that has no English translation, or whose translation is stale."""
    data, ontology = load_graphs(sources)
    items = localisation.pending(data, ontology)
    for item in items:
        click.echo(f"✘ {localisation.describe(item, data)}", err=True)
    if items:
        raise click.ClickException(f"{len(items)} item(s) need English.")
    click.echo("✔ Everything has English.")


@translations.command("export")
@click.option("--output", "-o", type=click.Path(dir_okay=False, path_type=Path), required=True)
@click.pass_obj
def translations_export(sources: Sources, output: Path) -> None:
    """Write a JSON worklist of what needs English. Fill each item's "translation" and run apply."""
    data, ontology = load_graphs(sources)
    items = localisation.pending(data, ontology)
    localisation.write_worklist(items, output)
    click.echo(f"✔ {len(items)} item(s) written to {output}")


@translations.command("apply")
@click.argument("worklist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--translated-by", required=True, help="Model identifier or translator name.")
@click.option("--method", type=click.Choice(sorted(localisation.METHODS)), default="machine", show_default=True)
@click.pass_obj
def translations_apply(sources: Sources, worklist: Path, translated_by: str, method: str) -> None:
    """Merge a filled-in worklist into data/translations/en/. New translations start as Draft."""
    items = localisation.read_worklist(worklist)
    missing = [item.subject for item in items if not item.translation]
    if missing:
        raise click.ClickException(f"{len(missing)} item(s) have no translation, e.g. {missing[0]}")
    for path in localisation.apply(sources.data_dir, items, translated_by, method, date.today()):
        click.echo(f"✔ Wrote {path}")
