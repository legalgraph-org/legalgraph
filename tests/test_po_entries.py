"""PO entries: parsing, keys and translations, and reading and writing whole files."""

from pathlib import Path

import pytest

from legalgraph.po import (
    PoEntry,
    parse_po_file,
    write_entries,
)


class TestPoEntry:
    """Test the PoEntry class."""

    def test_parse_simple_entry(self):
        """Test parsing a simple translated entry."""
        lines = [
            "#: app/page.tsx:10\n",
            'msgid "Hello"\n',
            'msgstr "Hallo"\n',
            "\n",
        ]
        entry = PoEntry(lines)

        assert entry.msgid == "Hello"
        assert entry.msgstr == "Hallo"
        assert entry.msgctxt is None
        assert entry.is_translated() is True
        assert entry.is_obsolete is False

    def test_parse_untranslated_entry(self):
        """Test parsing an untranslated entry."""
        lines = [
            "#: app/page.tsx:20\n",
            'msgid "Goodbye"\n',
            'msgstr ""\n',
            "\n",
        ]
        entry = PoEntry(lines)

        assert entry.msgid == "Goodbye"
        assert entry.msgstr == ""
        assert entry.is_translated() is False
        assert entry.is_obsolete is False

    def test_parse_obsolete_entry(self):
        """Test parsing an obsolete entry (marked with #~)."""
        lines = [
            "#: app/page.tsx:30\n",
            '#~ msgid "Old Feature"\n',
            '#~ msgstr "Alte Funktion"\n',
            "\n",
        ]
        entry = PoEntry(lines)

        assert entry.msgid == "Old Feature"
        assert entry.msgstr == "Alte Funktion"
        assert entry.is_obsolete is True
        assert entry.is_translated() is True

    def test_parse_obsolete_untranslated_entry(self):
        """Test parsing an obsolete untranslated entry"""
        lines = [
            "#: app/page.tsx:40\n",
            '#~ msgid "Old Untranslated"\n',
            '#~ msgstr ""\n',
            "\n",
        ]
        entry = PoEntry(lines)

        assert entry.msgid == "Old Untranslated"
        assert entry.msgstr == ""
        assert entry.is_obsolete is True
        assert entry.is_translated() is False

    def test_parse_multiline_entry(self):
        """Test parsing a multi-line entry."""
        lines = [
            "#: app/page.tsx:50\n",
            'msgid ""\n',
            '"This is a very long "\n',
            '"message that spans "\n',
            '"multiple lines"\n',
            'msgstr ""\n',
            '"Dies ist eine sehr lange "\n',
            '"Nachricht über "\n',
            '"mehrere Zeilen"\n',
            "\n",
        ]
        entry = PoEntry(lines)

        assert entry.msgid == "This is a very long message that spans multiple lines"
        assert entry.msgstr == "Dies ist eine sehr lange Nachricht über mehrere Zeilen"
        assert entry.is_translated() is True

    def test_parse_entry_with_context(self):
        """Test parsing an entry with msgctxt."""
        lines = [
            "#: app/page.tsx:60\n",
            'msgctxt "menu"\n',
            'msgid "File"\n',
            'msgstr "Datei"\n',
            "\n",
        ]
        entry = PoEntry(lines)

        assert entry.msgctxt == "menu"
        assert entry.msgid == "File"
        assert entry.msgstr == "Datei"
        assert entry.get_key() == ("menu", "File")

    def test_update_translation(self):
        """Test updating a translation."""
        lines = [
            "#: app/page.tsx:70\n",
            'msgid "Update Me"\n',
            'msgstr ""\n',
            "\n",
        ]
        entry = PoEntry(lines)

        assert entry.is_translated() is False

        entry.update_translation("Aktualisiere mich")

        assert entry.msgstr == "Aktualisiere mich"
        assert entry.is_translated() is True
        # Check that the lines were updated
        assert 'msgstr "Aktualisiere mich"\n' in entry.lines


class TestParsePoFile:
    """Test parsing PO files."""

    def test_parse_po_file(self, temp_po_file):
        """Test parsing a complete PO file."""
        po_file, _ = temp_po_file
        entries = parse_po_file(po_file)

        # Should have 7 entries: header + 6 message entries
        assert len(entries) == 7

        # Check header
        assert entries[0].msgid == ""
        assert entries[0].is_translated() is True

        # Check translated entry
        assert entries[1].msgid == "Hello World"
        assert entries[1].msgstr == "Hallo Welt"
        assert entries[1].is_obsolete is False

        # Check untranslated entry
        assert entries[2].msgid == "Goodbye"
        assert entries[2].msgstr == ""
        assert entries[2].is_obsolete is False

        # Check obsolete translated entry
        assert entries[4].msgid == "Obsolete Entry"
        assert entries[4].msgstr == "Veralteter Eintrag"
        assert entries[4].is_obsolete is True

        # Check obsolete untranslated entry (THE BUG CASE)
        assert entries[5].msgid == "Obsolete Untranslated"
        assert entries[5].msgstr == ""
        assert entries[5].is_obsolete is True

    def test_parse_nonexistent_file(self):
        """Test parsing a nonexistent file."""
        with pytest.raises(FileNotFoundError):
            parse_po_file("/nonexistent/file.po")


class TestWriteEntries:
    """Test writing entries to files."""

    def test_write_entries(self, temp_po_file):
        """Test writing entries to a file."""
        po_file, tmpdir = temp_po_file
        entries = parse_po_file(po_file)

        output_file = Path(tmpdir) / "output.po"
        write_entries(entries, str(output_file))

        assert output_file.exists()

        # Parse the output and compare
        output_entries = parse_po_file(str(output_file))
        assert len(output_entries) == len(entries)
