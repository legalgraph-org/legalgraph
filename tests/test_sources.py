"""Sources: verifying originals and annotated XML, extracting Turtle, fetching, rendering lines."""

import io
import shutil
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from source_helpers import by_id, with_annotated

from legalgraph import sources
from legalgraph.sources import Source
from legalgraph.sources.text import text_of


def test_every_source_verifies(all_sources: list[Source]) -> None:
    for source in all_sources:
        assert sources.verify(source) == [], source.id


def test_extracted_files_are_up_to_date(all_sources: list[Source]) -> None:
    for source in all_sources:
        assert source.output.read_text() == sources.extract(source), source.id


def test_extraction_is_deterministic(all_sources: list[Source]) -> None:
    for source in all_sources:
        assert sources.extract(source) == sources.extract(source)


def test_all_german_impressum_laws_are_covered(all_sources: list[Source]) -> None:
    german = {source.id for source in all_sources if source.jurisdiction == "DE"}
    assert german >= {"de/ddg", "de/mstv", "de/vsbg", "de/dlinfov", "de/gewo", "de/uwg", "de/ustg", "de/ao"}


def test_a_changed_word_in_official_xml_is_caught(all_sources: list[Source], tmp_path: Path) -> None:
    source = by_id(all_sources, "de/ddg")
    tampered = source.annotated.read_bytes().replace(b"Diensteanbieter", b"Anbieter", 1)
    errors = sources.verify(with_annotated(source, tmp_path, tampered))
    assert any("not byte-identical" in error for error in errors)


def test_a_changed_word_in_authored_xml_is_caught(all_sources: list[Source], tmp_path: Path) -> None:
    source = by_id(all_sources, "de/mstv")
    tampered = source.annotated.read_bytes().replace(b"Name und Anschrift sowie", b"Name sowie", 1)
    errors = sources.verify(with_annotated(source, tmp_path, tampered))
    assert any("does not occur word for word" in error for error in errors)


def test_authored_xml_must_follow_the_schema(all_sources: list[Source], tmp_path: Path) -> None:
    source = by_id(all_sources, "de/mstv")
    tampered = source.annotated.read_bytes().replace(b"<list>", b"<bullets>", 1).replace(b"</list>", b"</bullets>", 1)
    errors = sources.verify(with_annotated(source, tmp_path, tampered))
    assert any("bullets" in error for error in errors)


def test_an_edited_original_is_caught(all_sources: list[Source], tmp_path: Path) -> None:
    source = by_id(all_sources, "de/mstv")
    original = source.originals[0]
    copy = tmp_path / original.file.name
    copy.write_bytes(original.file.read_bytes() + b" ")
    errors = sources.verify(replace(source, originals=[replace(original, file=copy)]))
    assert any("SHA-256 differs" in error for error in errors)


def test_an_unknown_annotation_is_caught(all_sources: list[Source], tmp_path: Path) -> None:
    source = by_id(all_sources, "de/ddg")
    tampered = source.annotated.read_bytes().replace(b"<metadaten>", b'<metadaten lga:note="x">', 1)
    errors = sources.verify(with_annotated(source, tmp_path, tampered))
    assert any("unknown annotation" in error for error in errors)


def test_requires_outside_a_provision_is_rejected(all_sources: list[Source], tmp_path: Path) -> None:
    source = by_id(all_sources, "de/ddg")
    tampered = source.annotated.read_bytes().replace(b"<metadaten>", b'<metadaten lga:requires="VatId">', 1)
    with pytest.raises(sources.SourceError, match="outside a provision"):
        sources.extract(with_annotated(source, tmp_path, tampered))


def test_html_fragment_ignores_the_rest_of_the_page() -> None:
    page_a = (
        b'<html><head><meta name="token" content="a1"></head><body><div class="cont"><p>Text</p></div></body></html>'
    )
    page_b = (
        b'<html><head><meta name="token" content="b2"></head><body><div class="cont"><p>Text</p></div></body></html>'
    )
    assert sources.html_fragment(page_a, "div.cont") == sources.html_fragment(page_b, "div.cont")
    with pytest.raises(sources.SourceError, match="matched nothing"):
        sources.html_fragment(page_a, "div.missing")


def test_record_fetch_updates_the_index(all_sources: list[Source], tmp_path: Path) -> None:
    source = by_id(all_sources, "de/mstv")
    folder = tmp_path / "mstv"
    shutil.copytree(source.directory, folder)
    copy = sources.parse_index(folder / "source.yaml")
    assert sources.record_fetch(copy, copy.originals[0], b"<div>new text</div>\n", date(2027, 1, 2))
    updated = sources.parse_index(folder / "source.yaml").originals[0]
    assert updated.sha256 == sources.sha256(b"<div>new text</div>\n")
    assert updated.retrieved_on == date(2027, 1, 2)
    assert not sources.record_fetch(copy, updated, b"<div>new text</div>\n", date(2027, 1, 3))


def test_render_puts_list_items_on_their_own_lines() -> None:
    official = ET.fromstring(
        '<P>(1) Intro <DL><DT>1.</DT><DD><LA>first,</LA></DD><DT>2.</DT><DD><LA>second <FnR ID="x"/>'
        "<DL><DT>a)</DT><DD><LA>nested.</LA></DD></DL></LA></DD></DL></P>"
    )
    assert sources.render(official) == "(1) Intro\n1. first,\n2. second\na) nested."
    ns = sources.LAW_NS
    authored = ET.fromstring(
        f'<paragraph xmlns="{ns}" num="(2)">Intro <list><item num="1.">first,</item>'
        '<item num="2.">second.</item></list> Closing sentence.</paragraph>'
    )
    assert sources.render(authored) == "(2) Intro\n1. first,\n2. second.\nClosing sentence."


def test_reading_view_lines_are_the_quote_lines(all_sources: list[Source]) -> None:
    """The source-document pages pair each line with the translation's line, so the reading view
    must render a provision exactly as its quote."""
    for source in all_sources:
        extracted = sources.extract(source)
        for section in sources.reading_view(source):
            assert section["xml"].lstrip().startswith("<"), source.id
            for paragraph in section["paragraphs"]:
                if paragraph["provision"]:
                    text = "\n".join(line["text"] for line in paragraph["lines"])
                    assert text.replace('"', '\\"') in extracted, (source.id, paragraph["provision"])


def test_render_reads_formex() -> None:
    formex = ET.fromstring(
        "<PARAG><NO.PARAG>1.</NO.PARAG><ALINEA><P>Intro:</P><LIST><ITEM><NP><NO.P>(a)</NO.P>"
        '<TXT><QUOT.START CODE="2018"/>first<QUOT.END CODE="2019"/>;<NOTE><P>footnote</P></NOTE></TXT></NP></ITEM>'
        "<ITEM><NP><NO.P>(b)</NO.P><TXT>second.</TXT></NP></ITEM></LIST></ALINEA>"
        "<ALINEA>Second subparagraph.</ALINEA></PARAG>"
    )
    assert sources.render(formex) == "1. Intro:\n(a) ‘first’;\n(b) second.\nSecond subparagraph."


def test_gdpr_has_english_and_german_quotes(all_sources: list[Source]) -> None:
    extracted = sources.extract(by_id(all_sources, "eu/gdpr"))
    assert "lg:EU-2016-679-art13-1-q1-de" in extracted
    assert "lgo:languageVersionOf lg:EU-2016-679-art13-1-q1 ;" in extracted
    assert "(b) the contact details of the data protection officer, where applicable;" in extracted
    assert "b) gegebenenfalls die Kontaktdaten des Datenschutzbeauftragten;" in extracted


def test_a_pdf_without_a_unicode_map_is_read_in_its_code_page() -> None:
    """The Greek Government Gazette's old fonts show Windows-1253 bytes under Latin glyph names."""
    writer = PdfWriter()
    page = writer.add_blank_page(200, 200)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/BaseFont"): NameObject("/Times")})
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    content = DecodedStreamObject()
    # ΕΦΗΜΕΡΙΣ, then ΤΗΣ kerned in two parts on the next line.
    content.set_data(b"BT /F1 10 Tf 10 100 Td (\xc5\xd6\xc7\xcc\xc5\xd1\xc9\xd3) Tj T* [(\xd4) -20 (\xc7\xd3)] TJ ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    pdf = io.BytesIO()
    writer.write(pdf)

    assert text_of("application/pdf", pdf.getvalue(), [], "cp1253") == "ΕΦΗΜΕΡΙΣ ΤΗΣ"
