"""PO files: filling in missing translations, and the whole round trip."""

import tempfile
from pathlib import Path

import pytest

from legalgraph.po import (
    extract_missing_translations,
    merge_po_files,
    parse_po_file,
    split_po_file,
    update_missing_translations,
    write_entries,
)


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
