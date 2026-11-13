"""The command group and what every command shares: where the graph is, and loading it."""

from pathlib import Path

import click
from dotenv import load_dotenv as load_env_file
from rdflib import Graph

from legalgraph.load import DEFAULT_DATA_DIR, DEFAULT_ONTOLOGY_DIR, Sources, load_all, new_graph


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
    help="Directory of the ontology (classes, vocabularies, rules).",
)
@click.option(
    "--load-dotenv",
    type=click.Path(exists=True, path_type=Path),
    help="Load environment variables from this file.",
)
@click.pass_context
def cli(ctx: click.Context, data_dir: Path, ontology_dir: Path, load_dotenv: Path | None) -> None:
    """Load, validate, query and export legalgraph."""
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


def load_graphs(sources: Sources) -> tuple[Graph, Graph]:
    """Data and ontology, separately."""
    data, ontology, _, errors = load_all(sources)
    if errors:
        raise click.ClickException("Turtle syntax errors; run `legalgraph validate`.")
    return data, ontology
