"""Command line: legalgraph validate | stats | quotes | checklist | query | export | translations | sources | site |
po-files."""

import json
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import click
from rdflib import RDF, Graph, URIRef

from legalgraph import LGO, localisation, rules
from legalgraph import site as graph_site
from legalgraph import sources as law_sources
from legalgraph.load import DEFAULT_DATA_DIR, DEFAULT_ONTOLOGY_DIR, Sources, load_all, new_graph
from legalgraph.po_files_cli import po_files
from legalgraph.validate import validate as run_validation

QUERIES_DIR = DEFAULT_DATA_DIR.parent / "queries"
EXPORT_FORMATS = {"ttl": "turtle", "nt": "nt", "jsonld": "json-ld"}


@click.group()
@click.option(
    "--data-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DEFAULT_DATA_DIR,
    show_default=True,
    help="Directory of graph data (*.ttl, searched recursively).",
)
@click.option(
    "--ontology-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=DEFAULT_ONTOLOGY_DIR,
    show_default=True,
    help="Directory of the ontology (src/ and shapes/).",
)
@click.option(
    "--load-dotenv",
    type=click.Path(exists=True, path_type=Path),
    help="Load environment variables from this file.",
)
@click.pass_context
def cli(ctx: click.Context, data_dir: Path, ontology_dir: Path, load_dotenv: Path | None) -> None:
    """Load, validate, query and export legalgraph."""
    from dotenv import load_dotenv as load_env_file

    if load_dotenv:
        load_env_file(load_dotenv)
    elif Path(".env").exists():
        load_env_file(".env")
    ctx.obj = Sources(data_dir=data_dir, ontology_dir=ontology_dir)


def load_data(sources: Sources, with_ontology: bool = False) -> Graph:
    data, ontology, _, errors = load_all(sources)
    if errors:
        raise click.ClickException("Turtle syntax errors; run `legalgraph validate`.")
    if with_ontology:
        merged = new_graph()
        merged += data
        merged += ontology
        return merged
    return data


@cli.command()
@click.pass_obj
def validate(sources: Sources) -> None:
    """Check Turtle syntax, undefined terms and the ontology's SHACL shapes."""
    report = run_validation(sources)
    for error in report.errors:
        click.echo(f"✘ {error}", err=True)
    if not report.ok:
        raise click.ClickException(f"{len(report.errors)} problem(s) found.")
    click.echo(f"✔ Graph is valid ({report.triples} triples).")


@cli.command()
@click.pass_obj
def stats(sources: Sources) -> None:
    """Count resources by class."""
    data = load_data(sources)
    counts = Counter(
        data.qname(cls) for cls in data.objects(None, RDF.type) if isinstance(cls, URIRef) and cls.startswith(LGO)
    )
    for name, count in sorted(counts.items()):
        click.echo(f"{name:<28}{count:>5}")
    click.echo(f"{'triples':<28}{len(data):>5}")


def run_query(graph: Graph, sparql: str) -> tuple[list[str], list[list[str]]]:
    result = graph.query(sparql)
    columns = [str(variable) for variable in result.vars or []]
    rows = [["" if value is None else str(value) for value in row] for row in result]
    return columns, rows


def print_rows(columns: list[str], rows: list[list[str]], output: str) -> None:
    if output == "json":
        click.echo(json.dumps([dict(zip(columns, row, strict=True)) for row in rows], ensure_ascii=False, indent=2))
        return
    if output == "csv":
        import csv

        writer = csv.writer(sys.stdout)
        writer.writerow(columns)
        writer.writerows(rows)
        return
    for row in rows:
        click.echo(" | ".join(value.replace("\n", " ") for value in row))
    click.echo(f"({len(rows)} rows)")


@cli.command()
@click.argument("query", type=click.Path(path_type=Path))
@click.option("--output", type=click.Choice(["table", "csv", "json"]), default="table", show_default=True)
@click.option("--with-ontology", is_flag=True, help="Query data and ontology together (needed for labels).")
@click.pass_obj
def query(sources: Sources, query: Path, output: str, with_ontology: bool) -> None:
    """Run a SPARQL query file. A bare name looks in queries/ (e.g. `legalgraph query coverage`)."""
    if not query.exists():
        query = QUERIES_DIR / f"{query.name.removesuffix('.rq')}.rq"
    if not query.exists():
        raise click.ClickException(f"No such query: {query}")
    columns, rows = run_query(load_data(sources, with_ontology), query.read_text())
    print_rows(columns, rows, output)


@cli.command()
@click.option("--country", "-c", help="ISO code, e.g. DE, AT, EU.")
@click.pass_obj
def quotes(sources: Sources, country: str | None) -> None:
    """Print the key quotes, optionally for one jurisdiction."""
    _, rows = run_query(load_data(sources), (QUERIES_DIR / "quotes.rq").read_text())
    for jurisdiction, citation, lang, text, source, english, english_status in rows:
        if country and jurisdiction != country.upper():
            continue
        click.echo(click.style(f"{jurisdiction} · {citation} [{lang}]", bold=True))
        click.echo(text)
        if english:
            click.echo(click.style(f"English ({english_status}):", italic=True))
            click.echo(english)
        click.echo(click.style(source, dim=True) + "\n")


@cli.command()
@click.option("--fact", "-f", "facts", multiple=True, help="A condition that holds, e.g. SellsToConsumers. Repeatable.")
@click.option("--established-in", "-e", help="Where the business is established, as a jurisdiction code, e.g. AT.")
@click.option(
    "--market", "-m", "markets", multiple=True, help="Where it offers goods or services, e.g. EU or FR. Repeatable."
)
@click.option(
    "--scenario",
    "-s",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="A scenario file (scenarios/*.yaml) whose facts to use.",
)
@click.option("--questions", is_flag=True, help="List the conditions and the question for each, then exit.")
@click.pass_obj
def checklist(
    sources: Sources,
    facts: tuple[str, ...],
    established_in: str | None,
    markets: tuple[str, ...],
    scenario: Path | None,
    questions: bool,
) -> None:
    """What a business must do, given facts about it: the obligations of the rules layer that apply,
    with the information to disclose, the actions to take and the provisions behind each."""
    graph = load_data(sources, with_ontology=True)
    conditions, obligations = rules.load(graph)
    places = rules.jurisdictions(graph)
    if questions:
        click.echo(f"--established-in, --market: one of {', '.join(sorted(places))}")
        for condition in rules.asked(conditions):
            click.echo(f"{condition.id}: {condition.question}")
        return
    given, offered = set(facts), set(markets)
    if scenario:
        loaded = rules.load_scenario(scenario)
        given |= loaded.facts
        offered |= loaded.markets
        established_in = established_in or loaded.established_in
    unknown = ({established_in} - {None} | offered) - set(places)
    if unknown:
        raise click.ClickException(f"Unknown jurisdiction(s): {', '.join(sorted(unknown))}")
    try:
        found = rules.applicable(conditions, obligations, given, established_in, offered)
    except rules.RulesError as error:
        raise click.ClickException(f"{error}. List them with `legalgraph checklist --questions`.") from error
    established_in = rules.establishment(conditions, given, established_in)
    labels = {
        str(s): str(o)
        for s, o in graph.subject_objects(URIRef("http://www.w3.org/2004/02/skos/core#prefLabel"))
        if getattr(o, "language", None) in (None, "en")
    }
    citations = {str(s): str(o) for s, o in graph.subject_objects(LGO.citation)}

    def label(namespace: str, name: str) -> str:
        return labels.get(f"{namespace}{name}", name)

    for obligation in found:
        status = "" if obligation.status == "Reviewed" else " (draft)"
        click.echo(click.style(f"{obligation.applies_in} · {obligation.label}{status}", bold=True))
        for item in obligation.items:
            click.echo(f"  disclose: {label(str(rules.LGV), item)}")
        for action in obligation.actions:
            click.echo(f"  do: {label(str(rules.LGV), action)}")
        national = obligation.national(established_in)
        if national:
            in_force = ", ".join(citations.get(f"{rules.LG}{p}", p) for p in national)
            click.echo(f"  in {places[established_in]}: {in_force}")
        sources_text = ", ".join(citations.get(f"{rules.LG}{p}", p) for p in obligation.established_by)
        click.echo(click.style(f"  {sources_text} · lg:{obligation.id}", dim=True))
    if not found:
        click.echo("No obligation applies to these facts.")


@cli.group()
def translations() -> None:
    """English translations: check, export a worklist, apply a filled-in worklist."""


@translations.command("check")
@click.pass_obj
def translations_check(sources: Sources) -> None:
    """List text that has no English translation, or whose translation is stale."""
    data, ontology, _, errors = load_all(sources)
    if errors:
        raise click.ClickException("Turtle syntax errors; run `legalgraph validate`.")
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
    data, ontology, _, errors = load_all(sources)
    if errors:
        raise click.ClickException("Turtle syntax errors; run `legalgraph validate`.")
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
    from legalgraph import amendments as live_amendments

    results = live_amendments.run(list(ids), data_graph=load_data(sources))
    failed = [r for r in results if not r.ok]
    for r in results:
        marker = "ok" if r.ok else ("skip" if r.skipped else "FAIL")
        click.echo(f"{marker:4} {r.act:22} {r.message}")
    click.echo(f"{len(results) - len(failed)}/{len(results)} checks pass")
    if failed:
        raise click.ClickException(f"{len(failed)} amendment check(s) failed")


@cli.group()
def sources() -> None:
    """Official law texts: fetch them, verify the annotated XML, extract Turtle."""


def selected(ids: tuple[str, ...]) -> list[law_sources.Source]:
    try:
        return law_sources.load_sources(ids=ids)
    except law_sources.SourceError as error:
        raise click.ClickException(str(error)) from error


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
        return
    changed = 0
    for source in selected(ids):
        for original in source.originals:
            try:
                data = law_sources.fetch(original)
            except (OSError, law_sources.SourceError) as error:
                raise click.ClickException(f"{source.id} {original.file.name}: {error}") from error
            name = f"{source.id}/{original.file.name}"
            if law_sources.sha256(data) == original.sha256 or law_sources.same_text(original, data):
                click.echo(f"✔ {name}: unchanged")
                continue
            changed += 1
            if check:
                click.echo(
                    f"✘ {name}: the portal now serves different text (SHA-256 {law_sources.sha256(data)})", err=True
                )
            else:
                law_sources.record_fetch(source, original, data, date.today())
                click.echo(f"✔ {name}: updated; re-annotate and run `legalgraph sources verify`")
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
        for source in selected(ids):
            outputs.append((source.output, law_sources.extract(source)))
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


def site_data(sources: Sources) -> None:
    try:
        counts = graph_site.generate_data(sources)
    except graph_site.SiteError as error:
        raise click.ClickException(str(error)) from error
    summary = ", ".join(f"{count} {collection}" for collection, count in counts.items())
    click.echo(f"✔ Site data written to {graph_site.DATA_DIR} ({summary})")


@cli.command("generate-site")
@click.option("--data-only", is_flag=True, help="Write the data files only; skip the Astro build.")
@click.pass_obj
def generate_site(sources: Sources, data_only: bool) -> None:
    """Build the browsable site into site/dist, ready for Cloudflare Pages (needs bun)."""
    site_data(sources)
    if data_only:
        return
    try:
        graph_site.bun("run", "build")
    except (graph_site.SiteError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"✔ Site built in {graph_site.SITE_DIR / 'dist'}")


@cli.command("serve-site")
@click.option("--port", default=4321, show_default=True)
@click.option("--built", is_flag=True, help="Serve the built site (site/dist) instead of the dev server.")
@click.pass_obj
def serve_site(sources: Sources, port: int, built: bool) -> None:
    """Browse the graph locally. The dev server reloads on site changes; rerun after data changes."""
    site_data(sources)
    try:
        if built:
            graph_site.bun("run", "build")
            graph_site.bun("run", "preview", "--port", str(port))
        else:
            graph_site.bun("run", "dev", "--port", str(port))
    except (graph_site.SiteError, subprocess.CalledProcessError) as error:
        raise click.ClickException(str(error)) from error
    except KeyboardInterrupt:
        pass


@cli.command()
@click.option("--format", "fmt", type=click.Choice(sorted(EXPORT_FORMATS)), default="ttl", show_default=True)
@click.option("--output", "-o", type=click.Path(dir_okay=False, path_type=Path), required=True)
@click.option("--with-ontology", is_flag=True, help="Include ontology and vocabularies in the export.")
@click.pass_obj
def export(sources: Sources, fmt: str, output: Path, with_ontology: bool) -> None:
    """Merge all data files into one file (Turtle, N-Triples or JSON-LD)."""
    graph = load_data(sources, with_ontology)
    output.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=output, format=EXPORT_FORMATS[fmt])
    click.echo(f"✔ Wrote {len(graph)} triples to {output}")


# Splitting, merging and filling the site's gettext catalogs (site/locales/*.po) for translation.
cli.add_command(po_files)


if __name__ == "__main__":
    cli()
