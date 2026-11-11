import shutil
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from legalgraph import sources
from legalgraph.sources import Source


@pytest.fixture(scope="module")
def all_sources() -> list[Source]:
    found = sources.load_sources()
    assert found, "no sources/**/source.yaml found"
    return found


def by_id(all_sources: list[Source], source_id: str) -> Source:
    return next(source for source in all_sources if source.id == source_id)


def with_annotated(source: Source, tmp_path: Path, annotated: bytes) -> Source:
    path = tmp_path / source.annotated.name
    path.write_bytes(annotated)
    return replace(source, annotated=path)


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


def test_a_parallel_version_with_another_structure_is_caught(all_sources: list[Source], tmp_path: Path) -> None:
    source = by_id(all_sources, "eu/gdpr")
    parallel = source.parallels[0]
    copy = tmp_path / parallel.file.name
    # Drop point (b) of Article 13(1) from the German text: the line counts no longer match.
    text = parallel.file.read_bytes()
    start = text.index(b'<PARAG IDENTIFIER="013.001">')
    item = text.index(b"<ITEM><NP><NO.P>b)</NO.P>", start)
    copy.write_bytes(text[:item] + text[text.index(b"</ITEM>", item) + len(b"</ITEM>") :])
    changed = [
        replace(o, file=copy, sha256=sources.sha256(copy.read_bytes())) if o is parallel else o
        for o in source.originals
    ]
    errors = sources.verify(replace(source, originals=changed))
    assert any("EU-2016-679-art13-1 has 6 lines" in error for error in errors), errors


def test_a_corrigendum_of_a_quoted_provision_is_caught(all_sources: list[Source]) -> None:
    """When the annotated text is the Official Journal text itself, a corrigendum of a quoted provision
    must be applied first."""
    source = by_id(all_sources, "eu/gdpr-recitals")
    corrigendum = source.corrigenda[0]
    changed = [replace(o, corrects=[*o.corrects, "Recital 30"]) if o is corrigendum else o for o in source.originals]
    errors = sources.verify(replace(source, originals=changed))
    assert any("corrects Recital 30, which EU-2016-679-rec30 quotes" in error for error in errors), errors


def test_a_consolidated_text_must_match_the_authentic_text(all_sources: list[Source]) -> None:
    """Art. 37(1) GDPR reads differently in the consolidated text: only the 2018 corrigendum explains it."""
    source = by_id(all_sources, "eu/gdpr")
    assert sources.verify(source) == []
    unlisted = [
        replace(o, corrects=[c for c in o.corrects if c != "Art. 37(1)"]) if o.role == "corrigendum" else o
        for o in source.originals
    ]
    errors = sources.verify(replace(source, originals=unlisted))
    assert any("EU-2016-679-art37-1 differs from the authentic text" in error for error in errors), errors


def test_an_amended_provision_must_occur_in_the_amending_act(all_sources: list[Source], tmp_path: Path) -> None:
    source = by_id(all_sources, "eu/eprivacy")
    assert sources.verify(source) == []
    amendment = next(o for o in source.amendments if o.language == "en")
    copy = tmp_path / amendment.file.name
    copy.write_bytes(
        amendment.file.read_bytes().replace(b"is only allowed on condition that", b"is allowed on condition that", 1)
    )
    changed = [
        replace(o, file=copy, sha256=sources.sha256(copy.read_bytes())) if o is amendment else o
        for o in source.originals
    ]
    errors = sources.verify(replace(source, originals=changed))
    assert any("EU-2002-58-art5-3:" in error and "does not occur word for word" in error for error in errors), errors


def test_a_list_point_from_an_amending_act_ignores_only_its_final_punctuation(
    all_sources: list[Source], tmp_path: Path
) -> None:
    # The amending act quotes Art. 6(1)(c) ending in "acting." where the consolidated list point ends
    # in "acting;": that difference is tolerated, a changed word is not.
    source = by_id(all_sources, "eu/crd")
    assert sources.verify(source) == []
    amendment = next(o for o in source.amendments if o.file.name == "L_2019328EN.01000701.xml")
    copy = tmp_path / amendment.file.name
    original = amendment.file.read_bytes()
    assert b"telephone number and email address" in original
    copy.write_bytes(original.replace(b"telephone number and email address", b"telephone number or email address", 1))
    changed = [
        replace(o, file=copy, sha256=sources.sha256(copy.read_bytes())) if o is amendment else o
        for o in source.originals
    ]
    errors = sources.verify(replace(source, originals=changed))
    assert any("EU-2011-83-art6-1-c:" in error and "does not occur word for word" in error for error in errors), errors


def test_mechanical_references_within_an_eu_act(all_sources: list[Source]) -> None:
    extracted = sources.extract(by_id(all_sources, "eu/gdpr"))
    block = extracted[extracted.index("lg:EU-2016-679-art13-1\n") :]
    block = block[: block.index("\n\n")]
    refers = next(line for line in block.splitlines() if "lgo:refersTo" in line)
    assert "lg:EU-2016-679-art6-1" in refers and "lg:EU-2016-679-art46-1" in refers


def test_saved_url_reads_the_browser_marker() -> None:
    page = b"<!-- saved from url=(0049)https://zakon.rada.gov.ua/laws/show/1023-12/print -->\n<html></html>"
    assert sources.saved_url(page) == "https://zakon.rada.gov.ua/laws/show/1023-12/print"
    assert sources.saved_url(b"<html><body>not a saved page</body></html>") is None


def test_fetch_saved_cuts_the_fragment_like_a_download(all_sources: list[Source]) -> None:
    source = by_id(all_sources, "ua/language")
    original = source.texts[0]
    page = (
        b"<!-- saved from url=(0049)https://zakon.rada.gov.ua/laws/show/2704-19/print -->\n"
        b"<html><head><title>saved</title></head><body>"
        + original.file.read_bytes()
        + b"<p>browser chrome</p></body></html>"
    )
    data = sources.fetch_saved(original, page)
    assert sources.same_text(original, data)
    assert not sources.same_text(original, data + b"<p>changed</p>")


def test_as_of_needs_role_parallel(all_sources: list[Source], tmp_path: Path) -> None:
    source = by_id(all_sources, "ua/media")
    folder = tmp_path / "media"
    shutil.copytree(source.directory, folder)
    index = folder / "source.yaml"
    index.write_text(index.read_text().replace("media_type: text/html", "media_type: text/html\n    as_of: 2021-01-01"))
    with pytest.raises(sources.SourceError, match="parallel"):
        sources.parse_index(index)


def test_an_english_older_than_an_amendment_is_refused(all_sources: list[Source], tmp_path: Path) -> None:
    """The Rada's English of Article 27(6) predates the Media Law's 2022 rewrite of that paragraph:
    the portal's own amendment note is newer than the translation, so verify refuses it."""
    source = by_id(all_sources, "ua/language")
    parallel = source.parallels[0]
    stale = parallel.annotated.read_bytes().replace(
        b'<paragraph num="7." lga:provision="UA-2704-art27-7"',
        b'<paragraph num="6 ." lga:provision="UA-2704-art27-6" '
        b'lga:url="https://zakon.rada.gov.ua/laws/show/en/2704-19#n216">Translated text</paragraph>'
        b'<paragraph num="7." lga:provision="UA-2704-art27-7"',
    )
    copy = tmp_path / parallel.annotated.name
    copy.write_bytes(stale)
    originals = [replace(o, annotated=copy) if o is parallel else o for o in source.originals]
    errors = sources.verify(replace(source, originals=originals))
    assert any("UA-2704-art27-6" in error and "after the translation" in error for error in errors), errors


def test_authored_parallel_gives_official_english_quotes(all_sources: list[Source]) -> None:
    extracted = sources.extract(by_id(all_sources, "ua/language"))
    assert "lg:UA-2704-art27-7-q1-en" in extracted
    assert "lgo:languageVersionOf lg:UA-2704-art27-7-q1 ;" in extracted
    assert "must have a user interface version in the State language" in extracted
    # Article 27(6)'s official English predates its 2022 rewrite: no -en quote; it needs a translation.
    assert "lg:UA-2704-art27-6-q1-en" not in extracted


def test_authentic_text_check_ignores_quote_typography() -> None:
    xml = sources.authentic_form("corresponds to the data subject's consent", "application/xml")
    pdf = sources.authentic_form("corresponds to the data sub-\nject’s consent", "application/pdf")
    assert sources.authentic_form("data subject's", "application/pdf") in pdf
    assert "subject" in xml and sources.authentic_form("the data subject’s consent", "application/xml") in xml


def test_reannotate_carries_annotations_onto_a_refreshed_original() -> None:
    ns = f' xmlns:lga="{sources.ANNOTATION_NS}"'
    old = (
        f'<law{ns}><p lga:provision="X-1" lga:citation="§ 1 &amp; § 2">Old text</p><p>Same</p><br lga:note="a"/></law>'
    )
    new = b"<law><p>Old text</p><p>Same</p><br/><p>Added</p></law>"
    merged, problems = sources.reannotate(old.encode(), new)
    assert problems == []
    assert sources.strip_annotations(merged) == new
    parsed = ET.fromstring(merged)
    assert parsed.find("p").get(f"{{{sources.ANNOTATION_NS}}}citation") == "§ 1 & § 2"


def test_reannotate_leaves_a_changed_element_unannotated() -> None:
    ns = f' xmlns:lga="{sources.ANNOTATION_NS}"'
    old = f'<law{ns}><p lga:provision="X-1">Old text</p></law>'.encode()
    merged, problems = sources.reannotate(old, b"<law><p>New text</p></law>")
    assert problems == ["<p>: text changed, annotation left out"]
    assert b"lga:provision" not in merged
