"""
PO File Management Utilities

This module provides utilities for managing gettext PO (Portable Object) translation files.
It supports splitting large files into manageable chunks, merging them back, and handling
incremental translation updates.

Main Features:
    - Split large PO files into smaller chunks for easier translation
    - Merge translated chunks back into a single file
    - Extract only missing (untranslated) entries
    - Update source files with newly translated entries while preserving structure
    - Properly handle obsolete entries (marked with #~)
"""

import math
import os


class PoEntry:
    """
    Represents a single entry in a PO file.

    A PO entry typically consists of comments, msgctxt (optional), msgid, and msgstr.
    This class parses and manages these components while preserving the original
    formatting and structure.

    Attributes:
        lines (list): Raw lines from the PO file that make up this entry
        msgid (str): The message ID (source text)
        msgstr (str): The translated message
        msgctxt (str): Optional message context
        msgstr_index (int): Line index where msgstr starts within self.lines
        is_obsolete (bool): Whether this entry is marked as obsolete (#~)
    """

    def __init__(self, lines):
        """
        Initialize a PO entry from raw file lines.

        Args:
            lines (list): List of strings representing the raw lines of this entry
        """
        self.lines = lines
        self.msgid = None
        self.msgstr = None
        self.msgctxt = None
        self.msgstr_index = -1  # Line index within self.lines where msgstr starts
        self.is_obsolete = False
        self._parse()

    def _parse(self):
        """
        Parse the raw lines to extract msgid, msgstr, and msgctxt.

        This method processes the lines to identify and extract the key components
        of a PO entry. It handles multi-line strings and continuation lines.
        Also detects obsolete entries marked with #~.
        """
        current_token = None
        buffer = ""

        for i, line in enumerate(self.lines):
            stripped = line.strip()
            if not stripped:
                continue

            # Check if this is an obsolete entry
            if stripped.startswith("#~"):
                self.is_obsolete = True
                # Remove the #~ prefix for parsing
                stripped = stripped[2:].strip()

            if stripped.startswith("msgctxt"):
                current_token = "msgctxt"
                buffer = self._extract_string(stripped)
                self.msgctxt = buffer
            elif stripped.startswith("msgid"):
                current_token = "msgid"
                buffer = self._extract_string(stripped)
                self.msgid = buffer
            elif stripped.startswith("msgstr"):
                current_token = "msgstr"
                self.msgstr_index = i
                buffer = self._extract_string(stripped)
                self.msgstr = buffer
            elif stripped.startswith('"'):
                # Continuation line
                str_val = self._extract_string(stripped)
                if current_token == "msgid":
                    self.msgid += str_val
                elif current_token == "msgstr":
                    self.msgstr += str_val
                elif current_token == "msgctxt":
                    self.msgctxt += str_val

    def _extract_string(self, line):
        """
        Extract the string content from a PO file line.

        Extracts the content between quotes in a line like:
        msgid "content" or "continuation"

        Args:
            line (str): A line from the PO file

        Returns:
            str: The extracted string content (without quotes)
        """
        # Find first quote
        start = line.find('"')
        if start == -1:
            return ""

        # Find last unescaped quote
        end = -1
        idx = len(line) - 1
        while idx > start:
            if line[idx] == '"' and (idx == 0 or line[idx - 1] != "\\"):
                end = idx
                break
            idx -= 1

        if end > start:
            return line[start + 1 : end]
        return ""

    def is_translated(self):
        """
        Check if this entry has a translation.

        Returns:
            bool: True if msgstr is not None and not empty, False otherwise
        """
        return self.msgstr is not None and self.msgstr != ""

    def get_key(self):
        """
        Get a unique key for this entry.

        The key is a tuple of (msgctxt, msgid) which uniquely identifies
        a translation entry in a PO file.

        Returns:
            tuple: (msgctxt, msgid) tuple
        """
        return (self.msgctxt, self.msgid)

    def update_translation(self, new_translation):
        """
        Update the msgstr of this entry with a new translation.

        This method replaces the msgstr lines in self.lines with the new
        translation while preserving formatting and indentation.

        Args:
            new_translation (str): The new translation text to set
        """
        if self.msgstr_index == -1:
            return

        # Preserve indentation from original line
        prefix = self.lines[self.msgstr_index].split("msgstr")[0]

        # Create new msgstr line
        new_lines = [f'{prefix}msgstr "{new_translation}"\n']

        # Find where the old msgstr ends (next non-continuation line)
        end_index = self.msgstr_index + 1
        while end_index < len(self.lines):
            line = self.lines[end_index].strip()
            if line.startswith('"'):
                end_index += 1
            else:
                break

        # Replace the msgstr lines
        self.lines[self.msgstr_index : end_index] = new_lines
        self.msgstr = new_translation  # Update internal state


def parse_po_file(file_path):
    """
    Parse a PO file into a list of PoEntry objects.

    Reads the entire file and splits it into individual entries based on
    blank line separators. Each entry is wrapped in a PoEntry object.

    Args:
        file_path (str): Absolute path to the PO file

    Returns:
        list: List of PoEntry objects

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()

    entries = []
    current_lines = []

    for line in lines:
        # Blank lines separate entries in PO files
        if line.strip() == "":
            if current_lines:
                current_lines.append(line)  # Include the blank line
                entries.append(PoEntry(current_lines))
                current_lines = []
            else:
                # Multiple blank lines or start of file
                current_lines.append(line)
        else:
            current_lines.append(line)

    if current_lines:
        entries.append(PoEntry(current_lines))

    return entries


def write_entries(entries, output_path):
    """
    Write a list of PoEntry objects to a file.

    Args:
        entries (list): List of PoEntry objects to write
        output_path (str): Path where the file should be written
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.writelines(entry.lines)


def split_po_file(source_path, output_dir, num_chunks):
    """
    Split a PO file into multiple chunks.

    Args:
        source_path (str): Path to source PO file
        output_dir (str): Directory to store chunks
        num_chunks (int): Number of chunks to create

    Returns:
        list: List of created file paths
    """
    entries = parse_po_file(source_path)

    total = len(entries)
    chunk_size = math.ceil(total / num_chunks)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    created_files = []
    for i in range(num_chunks):
        start = i * chunk_size
        end = start + chunk_size
        chunk_entries = entries[start:end]

        if not chunk_entries:
            break

        out_name = os.path.join(output_dir, f"part_{i + 1:03d}.po")
        write_entries(chunk_entries, out_name)
        created_files.append(out_name)

    return created_files


def merge_po_files(source_path, chunks_dir):
    """
    Merge PO file chunks back into a single file.

    Args:
        source_path (str): Path to target PO file (will be overwritten)
        chunks_dir (str): Directory containing chunk files

    Returns:
        int: Number of files merged
    """
    files = sorted([f for f in os.listdir(chunks_dir) if f.endswith(".po")])

    all_entries = []
    for fname in files:
        path = os.path.join(chunks_dir, fname)
        entries = parse_po_file(path)
        all_entries.extend(entries)

    write_entries(all_entries, source_path)
    return len(files)


def extract_missing_translations(source_path, output_dir, chunk_size=50):
    """
    Extract missing translations to chunk files.

    Identifies all entries in the source file that have empty translations
    (msgstr == "") and writes them to separate chunk files for translation.
    The header entry (msgid == "") and obsolete entries (marked with #~) are skipped.

    Args:
        source_path (str): Path to source PO file
        output_dir (str): Directory to store chunks with missing translations
        chunk_size (int): Number of entries per chunk

    Returns:
        tuple: (number of missing entries, list of created files)
    """
    entries = parse_po_file(source_path)

    # Identify missing translations (excluding header and obsolete entries)
    missing_entries = []
    for e in entries:
        # Skip header (msgid "")
        if e.msgid == "":
            continue
        # Skip obsolete entries (marked with #~)
        if e.is_obsolete:
            continue
        # Only include untranslated entries
        if not e.is_translated():
            missing_entries.append(e)

    if not missing_entries:
        return 0, []

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Split into chunks
    num_chunks = math.ceil(len(missing_entries) / chunk_size)

    created_files = []
    for i in range(num_chunks):
        start = i * chunk_size
        end = start + chunk_size
        chunk = missing_entries[start:end]

        out_name = os.path.join(output_dir, f"missing_part_{i + 1:03d}.po")
        write_entries(chunk, out_name)
        created_files.append(out_name)

    return len(missing_entries), created_files


def update_missing_translations(source_path, chunks_dir):
    """
    Update source file with translated entries from chunks.

    Reads translations from chunk files and updates the source PO file.
    Only entries that are currently empty (untranslated) in the source
    will be updated. This preserves existing translations and file structure.

    Args:
        source_path (str): Path to source PO file to update
        chunks_dir (str): Directory containing translated chunk files

    Returns:
        int: Number of entries updated
    """
    # Load translations from chunks
    translation_map = {}  # (msgctxt, msgid) -> msgstr

    if not os.path.exists(chunks_dir):
        raise FileNotFoundError(f"Chunks directory not found: {chunks_dir}")

    files = sorted([f for f in os.listdir(chunks_dir) if f.endswith(".po")])

    for fname in files:
        path = os.path.join(chunks_dir, fname)
        entries = parse_po_file(path)
        for e in entries:
            if e.is_translated():
                translation_map[e.get_key()] = e.msgstr

    # Update source file
    source_entries = parse_po_file(source_path)
    updated_count = 0

    for e in source_entries:
        # Only update if currently NOT translated and not the header
        if not e.is_translated() and e.msgid != "":
            key = e.get_key()
            if key in translation_map:
                new_trans = translation_map[key]
                e.update_translation(new_trans)
                updated_count += 1

    write_entries(source_entries, source_path)
    return updated_count
