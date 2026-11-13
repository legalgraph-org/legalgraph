"""po-files: split, merge and fill the site's PO translation files."""

from collections.abc import Callable
from functools import wraps
from pathlib import Path

import click

from legalgraph.po.files import (
    extract_missing_translations,
    merge_po_files,
    split_po_file,
    update_missing_translations,
)


def reported(command: Callable[..., None]) -> Callable[..., None]:
    """Any error as one line and a failing exit code."""

    @wraps(command)
    def run(*args: object, **kwargs: object) -> None:
        try:
            command(*args, **kwargs)
        except Exception as error:
            raise click.ClickException(str(error)) from error

    return run


def list_files(files: list[Path]) -> None:
    for path in files:
        click.echo(f"   - {path}")


@click.group(name="po-files")
def po_files() -> None:
    """Manage PO translation files - split, merge, extract missing translations."""


@po_files.command("split")
@click.option("--source", required=True, help="Path to source .po file", type=click.Path(exists=True))
@click.option("--output", required=True, help="Directory to store chunks", type=click.Path())
@click.option("--chunks", type=int, default=20, help="Number of chunks (default: 20)")
@reported
def split(source: str, output: str, chunks: int) -> None:
    """Split a PO file into chunks for easier translation."""
    created = split_po_file(source, output, chunks)
    click.echo(f"✅ Created {len(created)} chunk files in {output}")
    list_files(created)


@po_files.command("merge")
@click.option("--source", required=True, help="Path to target .po file to overwrite", type=click.Path())
@click.option("--chunks-dir", required=True, help="Directory containing chunks", type=click.Path(exists=True))
@reported
def merge(source: str, chunks_dir: str) -> None:
    """Merge chunks back into a single PO file."""
    click.echo(f"✅ Merged {merge_po_files(source, chunks_dir)} files into {source}")


@po_files.command("extract-missing")
@click.option("--source", required=True, help="Path to source .po file", type=click.Path(exists=True))
@click.option("--output", required=True, help="Directory to store chunks", type=click.Path())
@click.option("--chunk-size", type=int, default=50, help="Entries per chunk (default: 50)")
@reported
def extract_missing(source: str, output: str, chunk_size: int) -> None:
    """Extract missing translations to chunks (excludes obsolete entries marked with #~)."""
    missing, created = extract_missing_translations(source, output, chunk_size)
    if missing == 0:
        click.echo("✅ No missing translations found.")
        return
    click.echo(f"✅ Found {missing} missing translations.")
    click.echo(f"   Created {len(created)} chunk files in {output}")
    list_files(created)


@po_files.command("update-missing")
@click.option("--source", required=True, help="Path to source .po file", type=click.Path(exists=True))
@click.option(
    "--chunks-dir", required=True, help="Directory containing translated chunks", type=click.Path(exists=True)
)
@reported
def update_missing(source: str, chunks_dir: str) -> None:
    """Update source file with translations from chunk files (only updates empty entries)."""
    click.echo(f"✅ Updated {update_missing_translations(source, chunks_dir)} entries in {source}")
