"""Fixtures shared by the tests: every source under sources/, and sample PO files."""

import tempfile
from pathlib import Path

import pytest

from legalgraph import sources
from legalgraph.sources import Source


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


@pytest.fixture(scope="module")
def all_sources() -> list[Source]:
    found = sources.load_sources()
    assert found, "no sources/**/source.yaml found"
    return found
