"""Official law texts: fetch them, verify the annotated XML, extract Turtle."""

from datetime import date
from pathlib import Path

import click

from legalgraph import sources as law_sources
from legalgraph.cli.main import cli


@cli.group()
def sources() -> None:
    """Official law texts: fetch them, verify the annotated XML, extract Turtle."""


def selected(ids: tuple[str, ...]) -> list[law_sources.Source]:
    try:
        return law_sources.load_sources(ids=ids)
    except law_sources.SourceError as error:
        raise click.ClickException(str(error)) from error


def take_saved(ids: tuple[str, ...], saved_files: tuple[Path, ...]) -> None:
    """Each browser-saved page, matched to an original by its `saved from url` marker."""
    known = selected(ids)
    for path in saved_files:
        page = path.read_bytes()
        url = law_sources.saved_url(page)
        if url is None:
            raise click.ClickException(f"{path}: no `saved from url` marker; save the page with the browser")
        found = [(s, o) for s in known for o in s.originals if law_sources.same_saved_url(url, o.url)]
        if not found:
            raise click.ClickException(f"{path}: saved from {url}, which no source.yaml lists")
        for source, original in found:
            try:
                data = law_sources.fetch_saved(original, page)
            except law_sources.SourceError as error:
                raise click.ClickException(f"{source.id} {original.file.name}: {error}") from error
            if law_sources.record_fetch(source, original, data, date.today()):
                click.echo(f"✔ {source.id}/{original.file.name}: saved from {path.name}")
            else:
                click.echo(f"✔ {source.id}/{original.file.name}: unchanged")


def fetch_one(source: law_sources.Source, original: law_sources.Original, check: bool) -> bool:
    """Download one original; True when the portal's text differs from the committed one."""
    try:
        data = law_sources.fetch(original)
    except (OSError, law_sources.SourceError) as error:
        raise click.ClickException(f"{source.id} {original.file.name}: {error}") from error
    name = f"{source.id}/{original.file.name}"
    # Markup-only drift counts as unchanged, but only against the committed file the index records.
    recorded = original.file.exists() and law_sources.sha256(original.file.read_bytes()) == original.sha256
    if law_sources.sha256(data) == original.sha256 or (recorded and law_sources.same_text(original, data)):
        click.echo(f"✔ {name}: unchanged")
        return False
    if check:
        click.echo(f"✘ {name}: the portal now serves different text (SHA-256 {law_sources.sha256(data)})", err=True)
    else:
        law_sources.record_fetch(source, original, data, date.today())
        click.echo(f"✔ {name}: updated; re-annotate and run `legalgraph sources verify`")
    return True


@sources.command("fetch")
@click.argument("ids", nargs=-1)
@click.option("--check", is_flag=True, help="Download and compare only; fail if a portal's text has changed.")
@click.option(
    "--saved",
    "saved_files",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    multiple=True,
    help="Take originals from browser-saved pages (saved as HTML) instead of downloading.",
)
def sources_fetch(ids: tuple[str, ...], check: bool, saved_files: tuple[Path, ...]) -> None:
    """Download originals as described in each source.yaml (all, or the given ids such as de/ddg).

    Without --check, changed files are written and their sha256 and retrieved_on updated in
    source.yaml. Annotated XML is never touched: re-check it with `legalgraph sources verify`.

    For portals that block automated downloads, save the page by hand in a browser and pass the
    file(s) with --saved: each page is matched to an original by its `saved from url` marker.
    """
    if saved_files:
        if check:
            raise click.ClickException("--saved and --check do not combine.")
        take_saved(ids, saved_files)
        return
    changed = sum(fetch_one(source, original, check) for source in selected(ids) for original in source.originals)
    if check and changed:
        raise click.ClickException(f"{changed} original(s) changed upstream.")


@sources.command("verify")
@click.argument("ids", nargs=-1)
def sources_verify(ids: tuple[str, ...]) -> None:
    """Check originals against their hashes and the annotated XML against the originals."""
    errors = [error for source in selected(ids) for error in law_sources.verify(source)]
    for error in errors:
        click.echo(f"✘ {error}", err=True)
    if errors:
        raise click.ClickException(f"{len(errors)} problem(s) found.")
    click.echo("✔ Originals match their hashes; annotated XML matches the originals.")


@sources.command("reannotate")
@click.argument("ids", nargs=-1)
def sources_reannotate(ids: tuple[str, ...]) -> None:
    """Carry lga: annotations onto a refreshed original when verify says they drifted.

    For each official-xml source whose annotated XML no longer equals the original,
    reannotate() re-inserts every lga: attribute at the same element paths and reports
    elements whose text changed (those are left unannotated for manual review)."""
    problems = []
    for source in selected(ids):
        if source.kind != "official-xml":
            continue
        original = source.texts[0].file if source.texts else None
        if original is None or not original.exists():
            continue
        annotated = source.annotated.read_bytes()
        if law_sources.strip_annotations(annotated) == original.read_bytes():
            continue
        merged, issues = law_sources.reannotate(annotated, original.read_bytes())
        source.annotated.write_bytes(merged)
        for issue in issues:
            problems.append(f"{source.id}: {issue}")
            click.echo(f"✘ {source.id}: {issue}", err=True)
        click.echo(f"✔ {source.id}: re-annotated")
    if problems:
        raise click.ClickException(f"{len(problems)} annotation(s) could not be carried over")


@sources.command("extract")
@click.argument("ids", nargs=-1)
@click.option("--check", is_flag=True, help="Fail if a generated file is out of date instead of writing it.")
def sources_extract(ids: tuple[str, ...], check: bool) -> None:
    """Generate data/extracted/<id>.ttl from each annotated XML, and (without ids)
    data/extracted/link-only.ttl from sources/link-only.yaml."""
    stale = []
    outputs: list[tuple[Path, str]] = []
    try:
        outputs += [(source.output, law_sources.extract(source)) for source in selected(ids)]
        if not ids and (references := law_sources.extract_link_only()) is not None:
            outputs.append((law_sources.LINK_ONLY_OUTPUT, references))
    except law_sources.SourceError as error:
        raise click.ClickException(str(error)) from error
    for output, turtle in outputs:
        current = output.read_text() if output.exists() else None
        if turtle == current:
            continue
        if check:
            stale.append(output)
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(turtle)
        click.echo(f"✔ Wrote {output}")
    if stale:
        for path in stale:
            click.echo(f"✘ {path} is out of date; run `legalgraph sources extract`", err=True)
        raise click.ClickException(f"{len(stale)} generated file(s) out of date.")
    if check:
        click.echo("✔ Generated files are up to date.")
