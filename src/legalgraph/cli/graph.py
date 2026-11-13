"""Commands on the graph as a whole: validate, stats, query, quotes, export."""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import click
from rdflib import RDF, Graph, URIRef

from legalgraph import LGO
from legalgraph.cli.main import cli, load_data
from legalgraph.load import DEFAULT_DATA_DIR, Sources
from legalgraph.validate import validate as run_validation

QUERIES_DIR = DEFAULT_DATA_DIR.parent / "queries"
EXPORT_FORMATS = {"ttl": "turtle", "nt": "nt", "jsonld": "json-ld"}


@cli.command()
@click.pass_obj
def validate(sources: Sources) -> None:
    """Check Turtle syntax, undefined terms and the ontology's SHACL shapes."""
    report = run_validation(sources)
    for error in report.errors:
        click.echo(f"✘ {error}", err=True)
    for warning in report.warnings:
        click.echo(f"⚠ {warning}", err=True)
    if not report.ok:
        raise click.ClickException(f"{len(report.errors)} problem(s) found.")
    warned = f", {len(report.warnings)} warning(s)" if report.warnings else ""
    click.echo(f"✔ Graph is valid ({report.triples} triples{warned}).")


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
