"""Splitting a PO file into chunks for translation, merging them back, and filling in only what is
missing while preserving the rest of the file (obsolete #~ entries included)."""

import math
from pathlib import Path

from legalgraph.po.entry import PoEntry


def parse_po_file(file_path: str | Path) -> list[PoEntry]:
    """The file's entries; a blank line ends an entry and stays with it."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    entries, current = [], []
    with path.open(encoding="utf-8") as file:
        lines = file.readlines()
    for line in lines:
        current.append(line)
        if line.strip() == "" and len(current) > 1:
            entries.append(PoEntry(current))
            current = []
    if current:
        entries.append(PoEntry(current))
    return entries


def write_entries(entries: list[PoEntry], output_path: str | Path) -> None:
    with Path(output_path).open("w", encoding="utf-8") as file:
        for entry in entries:
            file.writelines(entry.lines)


def write_chunks(entries: list[PoEntry], output_dir: str | Path, size: int, name: str) -> list[Path]:
    """The entries in files of `size` entries each, named <name>_001.po, <name>_002.po, …"""
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    if size <= 0:
        return []
    created = []
    for number, start in enumerate(range(0, len(entries), size), 1):
        path = folder / f"{name}_{number:03d}.po"
        write_entries(entries[start : start + size], path)
        created.append(path)
    return created


def chunk_files(chunks_dir: str | Path) -> list[Path]:
    return sorted(path for path in Path(chunks_dir).iterdir() if path.name.endswith(".po"))


def split_po_file(source_path: str | Path, output_dir: str | Path, num_chunks: int) -> list[Path]:
    """The file in at most `num_chunks` chunk files."""
    entries = parse_po_file(source_path)
    return write_chunks(entries, output_dir, math.ceil(len(entries) / num_chunks), "part")


def merge_po_files(source_path: str | Path, chunks_dir: str | Path) -> int:
    """Join the chunk files into source_path, overwriting it; the number of files merged."""
    files = chunk_files(chunks_dir)
    write_entries([entry for path in files for entry in parse_po_file(path)], source_path)
    return len(files)


def extract_missing_translations(
    source_path: str | Path, output_dir: str | Path, chunk_size: int = 50
) -> tuple[int, list[Path]]:
    """The untranslated entries in chunk files, leaving out the header (msgid "") and obsolete ones."""
    missing = [e for e in parse_po_file(source_path) if e.msgid != "" and not e.is_obsolete and not e.is_translated()]
    if not missing:
        return 0, []
    return len(missing), write_chunks(missing, output_dir, chunk_size, "missing_part")


def update_missing_translations(source_path: str | Path, chunks_dir: str | Path) -> int:
    """Fill the source's untranslated entries from translated chunk files; the number updated.
    Translations already in the source are never replaced."""
    if not Path(chunks_dir).exists():
        raise FileNotFoundError(f"Chunks directory not found: {chunks_dir}")
    translations = {
        entry.get_key(): entry.msgstr
        for path in chunk_files(chunks_dir)
        for entry in parse_po_file(path)
        if entry.is_translated()
    }
    entries = parse_po_file(source_path)
    updated = 0
    for entry in entries:
        if not entry.is_translated() and entry.msgid != "" and entry.get_key() in translations:
            entry.update_translation(translations[entry.get_key()] or "")
            updated += 1
    write_entries(entries, source_path)
    return updated
