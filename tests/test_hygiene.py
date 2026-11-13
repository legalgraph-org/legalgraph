"""The hygiene rules: the repository follows them, and each catches what it is meant to."""

from pathlib import Path

from legalgraph import hygiene
from legalgraph.load import REPO_ROOT

PREFIXES = """@prefix lgo: <https://legalgraph.org/ontology#> .
@prefix lgs: <https://legalgraph.org/shapes#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
"""


def write(root: Path, path: str, text: str) -> Path:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target


def ontology(root: Path) -> Path:
    """A small ontology that follows every rule."""
    write(root, "ontology/ontology.ttl", PREFIXES + "<https://legalgraph.org/ontology> a owl:Ontology .\n")
    write(
        root,
        "ontology/classes/Act.ttl",
        PREFIXES + "lgo:Act a owl:Class .\nlgo:title a owl:DatatypeProperty ; rdfs:domain lgo:Act .\n",
    )
    write(root, "ontology/properties/text.ttl", PREFIXES + "lgo:text a owl:DatatypeProperty .\n")
    write(root, "ontology/rules/validation/ActShape.ttl", PREFIXES + "lgs:ActShape a sh:NodeShape .\n")
    write(
        root,
        "ontology/rules/reasoning/ActRule.ttl",
        PREFIXES + "lgs:ActRule a sh:NodeShape ; sh:rule [ a sh:TripleRule ] .\n",
    )
    return root


def codes(root: Path) -> list[str]:
    return [finding.code for finding in hygiene.check(root)]


def test_the_repository_follows_its_hygiene_rules() -> None:
    assert [finding.show(REPO_ROOT) for finding in hygiene.check(REPO_ROOT)] == []


def test_a_clean_tree_has_no_findings(tmp_path: Path) -> None:
    ontology(tmp_path)
    write(tmp_path, "src/pkg/module.py", '"""What it is for."""\n')
    assert codes(tmp_path) == []


def test_a_long_python_file_is_caught(tmp_path: Path) -> None:
    ontology(tmp_path)
    write(tmp_path, "tests/test_long.py", "x = 1\n" * 301)
    assert codes(tmp_path) == ["PY001"]


def test_a_module_without_docstring_is_caught(tmp_path: Path) -> None:
    ontology(tmp_path)
    write(tmp_path, "src/pkg/module.py", "x = 1\n")
    assert codes(tmp_path) == ["PY002"]


def test_an_unknown_ontology_folder_is_caught(tmp_path: Path) -> None:
    ontology(tmp_path)
    write(tmp_path, "ontology/src/old.ttl", PREFIXES)
    write(tmp_path, "ontology/rules/inference/Rule.ttl", PREFIXES)
    assert codes(tmp_path) == ["ONT001", "ONT001"]


def test_a_class_outside_its_own_file_is_caught(tmp_path: Path) -> None:
    ontology(tmp_path)
    write(tmp_path, "ontology/classes/Act.ttl", PREFIXES + "lgo:Act a owl:Class .\nlgo:Quote a owl:Class .\n")
    write(tmp_path, "ontology/vocab/terms.ttl", PREFIXES + "lgo:Term a owl:Class .\n")
    findings = hygiene.check(tmp_path, {"ONT002"})
    assert [(f.path.name, f.message) for f in findings] == [
        ("Act.ttl", "defines Act, Quote; a class file defines lgo:Act only"),
        ("terms.ttl", "lgo:Term belongs in classes/Term.ttl"),
    ]


def test_a_property_away_from_its_class_is_caught(tmp_path: Path) -> None:
    ontology(tmp_path)
    write(
        tmp_path,
        "ontology/properties/title.ttl",
        PREFIXES + "lgo:date a owl:DatatypeProperty ; rdfs:domain lgo:Act .\n",
    )
    findings = hygiene.check(tmp_path, {"ONT003"})
    assert [f.message for f in findings] == ["lgo:date belongs in classes/Act.ttl"]


def test_a_shape_named_unlike_its_file_is_caught(tmp_path: Path) -> None:
    ontology(tmp_path)
    write(tmp_path, "ontology/rules/validation/QuoteShape.ttl", PREFIXES + "lgs:Other a sh:NodeShape .\n")
    write(tmp_path, "ontology/rules/validation/ActRule.ttl", PREFIXES + "lgs:ActRule a sh:NodeShape ; sh:rule [] .\n")
    findings = hygiene.check(tmp_path, {"ONT004"})
    assert sorted(f.message for f in findings) == [
        "defines Other; the file defines lgs:QuoteShape only",
        "reasoning/ holds sh:rule shapes, validation/ shapes without sh:rule",
    ]
