"""
Unit tests for PO file utilities.

These tests cover all functionality including the bug fix for obsolete entries.
"""

import tempfile
from pathlib import Path

import pytest

from legalgraph.po_file_utils import (
    PoEntry,
    extract_missing_translations,
    merge_po_files,
    parse_po_file,
    split_po_file,
    update_missing_translations,
    write_entries,
)


@pytest.fixture
def sample_po_content():
    """Sample PO file content with various entry types."""
    return """msgid ""
msgstr ""
"POT-Creation-Date: 2025-08-10 20:45+0200\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=utf-8\\n"

#: app/page.tsx:10
msgid "Hello World"
msgstr "Hallo Welt"

#: app/page.tsx:20
msgid "Goodbye"
msgstr ""

#: app/page.tsx:30
msgid "Welcome"
msgstr "Willkommen"

#: app/page.tsx:40
#~ msgid "Obsolete Entry"
#~ msgstr "Veralteter Eintrag"

#: app/page.tsx:50
#~ msgid "Obsolete Untranslated"
#~ msgstr ""

#: app/page.tsx:60
msgid "Another Missing"
msgstr ""

"""


@pytest.fixture
def temp_po_file(sample_po_content):
    """Create a temporary PO file for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        po_file = Path(tmpdir) / "test.po"
        po_file.write_text(sample_po_content)
        yield str(po_file), tmpdir


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


class TestSplitPoFile:
    """Test splitting PO files into chunks."""

    def test_split_po_file(self, temp_po_file):
        """Test splitting a PO file into chunks."""
        po_file, tmpdir = temp_po_file
        output_dir = Path(tmpdir) / "chunks"

        created_files = split_po_file(po_file, str(output_dir), num_chunks=3)

        assert len(created_files) == 3
        assert output_dir.exists()

        # Check that all chunks exist
        for f in created_files:
            assert Path(f).exists()

        # Verify total entries match
        total_entries = 0
        for f in created_files:
            entries = parse_po_file(f)
            total_entries += len(entries)

        original_entries = parse_po_file(po_file)
        assert total_entries == len(original_entries)


class TestMergePoFiles:
    """Test merging PO file chunks."""

    def test_merge_po_files(self, temp_po_file):
        """Test merging chunks back into a single file."""
        po_file, tmpdir = temp_po_file
        chunks_dir = Path(tmpdir) / "chunks"
        output_file = Path(tmpdir) / "merged.po"

        # First split
        split_po_file(po_file, str(chunks_dir), num_chunks=3)

        # Then merge
        num_files = merge_po_files(str(output_file), str(chunks_dir))

        assert num_files == 3
        assert output_file.exists()

        # Verify content matches original
        original_entries = parse_po_file(po_file)
        merged_entries = parse_po_file(str(output_file))

        assert len(merged_entries) == len(original_entries)


class TestExtractMissingTranslations:
    """Test extracting missing translations - THIS TESTS THE BUG FIX."""

    def test_extract_missing_excludes_obsolete(self, temp_po_file):
        """
        Test that extract_missing correctly excludes obsolete entries.

        This is the main bug fix test. The bug was that obsolete entries
        (marked with #~) were being extracted as "missing" even though
        they should be ignored.
        """
        po_file, tmpdir = temp_po_file
        output_dir = Path(tmpdir) / "missing"

        num_missing, created_files = extract_missing_translations(po_file, str(output_dir), chunk_size=10)

        # Should find exactly 2 missing translations:
        # - "Goodbye" (line 20)
        # - "Another Missing" (line 60)
        # Should NOT include:
        # - Header (msgid "")
        # - "Obsolete Untranslated" (obsolete entry marked with #~)
        assert num_missing == 2, f"Expected 2 missing translations, got {num_missing}"

        assert len(created_files) == 1
        assert output_dir.exists()

        # Verify the extracted entries
        extracted_entries = parse_po_file(created_files[0])
        assert len(extracted_entries) == 2

        # Check that the correct entries were extracted
        msgids = [e.msgid for e in extracted_entries]
        assert "Goodbye" in msgids
        assert "Another Missing" in msgids
        assert "Obsolete Untranslated" not in msgids
        assert "Obsolete Entry" not in msgids

    def test_extract_missing_excludes_header(self, temp_po_file):
        """Test that extract_missing excludes the header entry."""
        po_file, tmpdir = temp_po_file
        output_dir = Path(tmpdir) / "missing"

        num_missing, created_files = extract_missing_translations(po_file, str(output_dir), chunk_size=10)

        # Verify header is not included
        extracted_entries = parse_po_file(created_files[0])
        for entry in extracted_entries:
            assert entry.msgid != "", "Header should not be in missing translations"

    def test_extract_missing_no_missing(self):
        """Test extract_missing when there are no missing translations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a PO file with all translations complete
            po_file = Path(tmpdir) / "complete.po"
            po_file.write_text("""msgid ""
msgstr ""

#: app/page.tsx:10
msgid "Hello"
msgstr "Hallo"

#: app/page.tsx:20
msgid "Goodbye"
msgstr "Auf Wiedersehen"

""")
            output_dir = Path(tmpdir) / "missing"

            num_missing, created_files = extract_missing_translations(str(po_file), str(output_dir), chunk_size=10)

            assert num_missing == 0
            assert len(created_files) == 0

    def test_extract_missing_chunking(self):
        """Test that extract_missing correctly chunks large numbers of missing entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a PO file with many missing translations
            po_content = 'msgid ""\nmsgstr ""\n\n'
            for i in range(25):
                po_content += f'#: app/page.tsx:{i}\nmsgid "Missing {i}"\nmsgstr ""\n\n'

            po_file = Path(tmpdir) / "many_missing.po"
            po_file.write_text(po_content)
            output_dir = Path(tmpdir) / "missing"

            num_missing, created_files = extract_missing_translations(str(po_file), str(output_dir), chunk_size=10)

            assert num_missing == 25
            assert len(created_files) == 3  # 10 + 10 + 5

            # Verify total entries across chunks
            total_entries = 0
            for f in created_files:
                entries = parse_po_file(f)
                total_entries += len(entries)

            assert total_entries == 25


class TestUpdateMissingTranslations:
    """Test updating source file with translated entries."""

    def test_update_missing_translations(self):
        """Test updating missing translations from chunks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file with missing translations
            source_file = Path(tmpdir) / "source.po"
            source_file.write_text("""msgid ""
msgstr ""

#: app/page.tsx:10
msgid "Hello"
msgstr ""

#: app/page.tsx:20
msgid "Goodbye"
msgstr ""

#: app/page.tsx:30
msgid "Welcome"
msgstr "Willkommen"

""")

            # Create chunks directory with translations
            chunks_dir = Path(tmpdir) / "chunks"
            chunks_dir.mkdir()

            chunk_file = chunks_dir / "chunk_001.po"
            chunk_file.write_text("""#: app/page.tsx:10
msgid "Hello"
msgstr "Hallo"

#: app/page.tsx:20
msgid "Goodbye"
msgstr "Auf Wiedersehen"

""")

            # Update the source file
            updated_count = update_missing_translations(str(source_file), str(chunks_dir))

            assert updated_count == 2

            # Verify the updates
            entries = parse_po_file(str(source_file))
            translations = {e.msgid: e.msgstr for e in entries if e.msgid}

            assert translations["Hello"] == "Hallo"
            assert translations["Goodbye"] == "Auf Wiedersehen"
            assert translations["Welcome"] == "Willkommen"  # Should remain unchanged

    def test_update_missing_preserves_existing(self):
        """Test that update_missing doesn't overwrite existing translations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file with existing translation
            source_file = Path(tmpdir) / "source.po"
            source_file.write_text("""msgid ""
msgstr ""

#: app/page.tsx:10
msgid "Hello"
msgstr "Existing Translation"

""")

            # Create chunks directory with different translation
            chunks_dir = Path(tmpdir) / "chunks"
            chunks_dir.mkdir()

            chunk_file = chunks_dir / "chunk_001.po"
            chunk_file.write_text("""#: app/page.tsx:10
msgid "Hello"
msgstr "New Translation"

""")

            # Update the source file
            updated_count = update_missing_translations(str(source_file), str(chunks_dir))

            # Should not update existing translation
            assert updated_count == 0

            # Verify the original translation is preserved
            entries = parse_po_file(str(source_file))
            translations = {e.msgid: e.msgstr for e in entries if e.msgid}

            assert translations["Hello"] == "Existing Translation"

    def test_update_missing_nonexistent_chunks_dir(self):
        """Test update_missing with nonexistent chunks directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = Path(tmpdir) / "source.po"
            source_file.write_text('msgid ""\nmsgstr ""\n')

            with pytest.raises(FileNotFoundError):
                update_missing_translations(str(source_file), "/nonexistent/chunks")


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_full_workflow_split_translate_merge(self):
        """Test the complete workflow: split -> translate -> merge."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            source_file = Path(tmpdir) / "source.po"
            source_file.write_text("""msgid ""
msgstr ""

#: app/page.tsx:10
msgid "Hello"
msgstr ""

#: app/page.tsx:20
msgid "Goodbye"
msgstr ""

#: app/page.tsx:30
msgid "Welcome"
msgstr ""

""")

            # Split into chunks
            chunks_dir = Path(tmpdir) / "chunks"
            created_files = split_po_file(str(source_file), str(chunks_dir), num_chunks=2)

            # "Translate" the chunks (manually update them)
            for chunk_file in created_files:
                entries = parse_po_file(chunk_file)
                for entry in entries:
                    if entry.msgid == "Hello":
                        entry.update_translation("Hallo")
                    elif entry.msgid == "Goodbye":
                        entry.update_translation("Auf Wiedersehen")
                    elif entry.msgid == "Welcome":
                        entry.update_translation("Willkommen")
                write_entries(entries, chunk_file)

            # Merge back
            output_file = Path(tmpdir) / "translated.po"
            merge_po_files(str(output_file), str(chunks_dir))

            # Verify all translations are present
            entries = parse_po_file(str(output_file))
            translations = {e.msgid: e.msgstr for e in entries if e.msgid}

            assert translations["Hello"] == "Hallo"
            assert translations["Goodbye"] == "Auf Wiedersehen"
            assert translations["Welcome"] == "Willkommen"

    def test_full_workflow_extract_missing_update(self):
        """Test the workflow: extract missing -> translate -> update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file with some translations and some missing
            source_file = Path(tmpdir) / "source.po"
            source_file.write_text("""msgid ""
msgstr ""

#: app/page.tsx:10
msgid "Hello"
msgstr "Hallo"

#: app/page.tsx:20
msgid "Goodbye"
msgstr ""

#: app/page.tsx:30
msgid "Welcome"
msgstr ""

#: app/page.tsx:40
#~ msgid "Obsolete"
#~ msgstr ""

""")

            # Extract missing
            missing_dir = Path(tmpdir) / "missing"
            num_missing, created_files = extract_missing_translations(str(source_file), str(missing_dir), chunk_size=10)

            # Should extract 2 (not the obsolete one)
            assert num_missing == 2

            # "Translate" the missing entries
            for chunk_file in created_files:
                entries = parse_po_file(chunk_file)
                for entry in entries:
                    if entry.msgid == "Goodbye":
                        entry.update_translation("Auf Wiedersehen")
                    elif entry.msgid == "Welcome":
                        entry.update_translation("Willkommen")
                write_entries(entries, chunk_file)

            # Update source file
            updated_count = update_missing_translations(str(source_file), str(missing_dir))

            assert updated_count == 2

            # Verify all translations
            entries = parse_po_file(str(source_file))
            translations = {e.msgid: e.msgstr for e in entries if e.msgid and not e.is_obsolete}

            assert translations["Hello"] == "Hallo"
            assert translations["Goodbye"] == "Auf Wiedersehen"
            assert translations["Welcome"] == "Willkommen"
