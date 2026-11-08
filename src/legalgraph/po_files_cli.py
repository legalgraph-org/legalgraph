"""PO file management CLI commands."""

import sys

import click

from legalgraph.po_file_utils import (
    extract_missing_translations,
    merge_po_files,
    split_po_file,
    update_missing_translations,
)


@click.group(name="po-files")
def po_files():
    """Manage PO translation files - split, merge, extract missing translations."""
    pass


@po_files.command("split")
@click.option("--source", required=True, help="Path to source .po file", type=click.Path(exists=True))
@click.option("--output", required=True, help="Directory to store chunks", type=click.Path())
@click.option("--chunks", type=int, default=20, help="Number of chunks (default: 20)")
def split(source, output, chunks):
    """Split a PO file into chunks for easier translation."""
    try:
        created_files = split_po_file(source, output, chunks)
        click.echo(f"✅ Created {len(created_files)} chunk files in {output}")
        for f in created_files:
            click.echo(f"   - {f}")
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        sys.exit(1)


@po_files.command("merge")
@click.option("--source", required=True, help="Path to target .po file to overwrite", type=click.Path())
@click.option("--chunks-dir", required=True, help="Directory containing chunks", type=click.Path(exists=True))
def merge(source, chunks_dir):
    """Merge chunks back into a single PO file."""
    try:
        num_files = merge_po_files(source, chunks_dir)
        click.echo(f"✅ Merged {num_files} files into {source}")
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        sys.exit(1)


@po_files.command("extract-missing")
@click.option("--source", required=True, help="Path to source .po file", type=click.Path(exists=True))
@click.option("--output", required=True, help="Directory to store chunks", type=click.Path())
@click.option("--chunk-size", type=int, default=50, help="Entries per chunk (default: 50)")
def extract_missing(source, output, chunk_size):
    """Extract missing translations to chunks (excludes obsolete entries marked with #~)."""
    try:
        num_missing, created_files = extract_missing_translations(source, output, chunk_size)

        if num_missing == 0:
            click.echo("✅ No missing translations found.")
            return

        click.echo(f"✅ Found {num_missing} missing translations.")
        click.echo(f"   Created {len(created_files)} chunk files in {output}")
        for f in created_files:
            click.echo(f"   - {f}")
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        sys.exit(1)


@po_files.command("update-missing")
@click.option("--source", required=True, help="Path to source .po file", type=click.Path(exists=True))
@click.option(
    "--chunks-dir", required=True, help="Directory containing translated chunks", type=click.Path(exists=True)
)
def update_missing(source, chunks_dir):
    """Update source file with translations from chunk files (only updates empty entries)."""
    try:
        updated_count = update_missing_translations(source, chunks_dir)
        click.echo(f"✅ Updated {updated_count} entries in {source}")
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        sys.exit(1)
