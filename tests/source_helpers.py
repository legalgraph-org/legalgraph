"""Helpers for the tests of sources/: finding a source, and swapping in another annotated XML."""

from dataclasses import replace
from pathlib import Path

from legalgraph.sources import Source


def by_id(all_sources: list[Source], source_id: str) -> Source:
    return next(source for source in all_sources if source.id == source_id)


def with_annotated(source: Source, tmp_path: Path, annotated: bytes) -> Source:
    path = tmp_path / source.annotated.name
    path.write_bytes(annotated)
    return replace(source, annotated=path)
