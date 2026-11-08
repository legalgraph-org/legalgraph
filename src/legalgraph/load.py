"""Finding and parsing the Turtle files of the graph and the ontology."""

from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph

from legalgraph import PREFIXES

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data"
DEFAULT_ONTOLOGY_DIR = REPO_ROOT / "ontology"


@dataclass
class ParseError:
    path: Path
    message: str


def turtle_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.ttl"))


def new_graph() -> Graph:
    graph = Graph()
    for prefix, namespace in PREFIXES.items():
        graph.bind(prefix, namespace)
    return graph


def parse_files(paths: list[Path]) -> tuple[Graph, list[ParseError]]:
    """Parse every file into one graph, collecting syntax errors instead of stopping at the first."""
    graph = new_graph()
    errors: list[ParseError] = []
    for path in paths:
        try:
            graph.parse(path, format="turtle")
        except Exception as error:  # rdflib raises several unrelated types for bad Turtle
            errors.append(ParseError(path, str(error)))
    return graph, errors


@dataclass
class Sources:
    data_dir: Path
    ontology_dir: Path

    @property
    def data_files(self) -> list[Path]:
        return turtle_files(self.data_dir)

    @property
    def ontology_files(self) -> list[Path]:
        return turtle_files(self.ontology_dir / "src")

    @property
    def shape_files(self) -> list[Path]:
        return turtle_files(self.ontology_dir / "shapes")


def load_all(sources: Sources) -> tuple[Graph, Graph, Graph, list[ParseError]]:
    """Data, ontology (classes, properties, vocabularies) and shapes graphs, plus any parse errors."""
    if not sources.ontology_dir.is_dir():
        raise FileNotFoundError(
            f"Ontology not found at {sources.ontology_dir} (it is the ontology/ folder of this repo)."
        )
    data, data_errors = parse_files(sources.data_files)
    ontology, ontology_errors = parse_files(sources.ontology_files)
    shapes, shape_errors = parse_files(sources.shape_files)
    return data, ontology, shapes, data_errors + ontology_errors + shape_errors
