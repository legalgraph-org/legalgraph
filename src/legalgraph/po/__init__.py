"""gettext PO files of the site (site/locales/*.po): split into chunks for translation, merged back,
and filled in where translations are missing, preserving the file's structure and obsolete entries."""

from legalgraph.po.entry import PoEntry
from legalgraph.po.files import (
    extract_missing_translations,
    merge_po_files,
    parse_po_file,
    split_po_file,
    update_missing_translations,
    write_entries,
)

__all__ = [
    "PoEntry",
    "extract_missing_translations",
    "merge_po_files",
    "parse_po_file",
    "split_po_file",
    "update_missing_translations",
    "write_entries",
]
