"""Sources in several versions: parallel languages, corrigenda, consolidations, translations and
refreshed originals."""

import shutil
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest
from source_helpers import by_id

from legalgraph import sources
from legalgraph.sources import Source


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


def test_a_mirrors_words_are_checked_against_the_official_text(all_sources: list[Source], tmp_path: Path) -> None:
    """Sourcing and checking apart: cz/zos-634 is taken from a mirror and verified against e-Sbírka."""
    source = by_id(all_sources, "cz/zos-634")
    assert sources.verify(source) == []
    official = next(o for o in source.originals if o.role == "authentic")
    changed = official.file.read_bytes().replace("mimosoudního řešení".encode(), "soudního řešení".encode())
    copy = tmp_path / official.file.name
    copy.write_bytes(changed)
    altered = replace(official, file=copy, sha256=sources.sha256(changed))
    tampered = replace(source, originals=[o if o is not official else altered for o in source.originals])
    errors = sources.verify(tampered)
    assert errors and all("does not occur word for word in 634-1992.esbirka.html" in e for e in errors)


def test_extraction_states_how_authentic_a_document_is(all_sources: list[Source]) -> None:
    mirror = sources.extract(by_id(all_sources, "cz/zos-634"))
    assert "lg:CZ-ZOS-634-source" in mirror
    assert "lgo:authenticity lgv:VerifiedAgainstOfficial" in mirror
    assert "lgo:verifiedAgainst lg:CZ-ZOS-634-source-official" in mirror
    unchecked = sources.extract(by_id(all_sources, "pt/csc"))
    assert "lgo:authenticity lgv:NotVerified" in unchecked
    official = sources.extract(by_id(all_sources, "cz/480-2004"))
    assert "lgo:authenticity lgv:Official" in official and "VerifiedAgainstOfficial" not in official
