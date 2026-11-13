"""PO files: splitting, merging, extracting and filling in missing translations."""

import tempfile
from pathlib import Path

from legalgraph.po import (
    extract_missing_translations,
    merge_po_files,
    parse_po_file,
    split_po_file,
)


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

        _, created_files = extract_missing_translations(po_file, str(output_dir), chunk_size=10)

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
