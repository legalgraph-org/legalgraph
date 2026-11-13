"""verify: the originals are the committed bytes, and the annotated XML is true to them.

official-xml: without its lga: attributes the annotated XML is the original byte for byte, its
parallel language versions have the same structure, and EU texts have their corrigenda applied or
their consolidation explained. authored-xml: the XML is valid against schemas/law.xsd and every
paragraph occurs word for word in its original; translations written the same way are checked alike.
"""

import xml.etree.ElementTree as ET

from lxml import etree

from legalgraph.sources.annotate import strip_annotations
from legalgraph.sources.consolidation import verify_consolidation, verify_corrigenda
from legalgraph.sources.constants import (
    ITEM_ATTRIBUTES,
    LAW_NS,
    LAW_SCHEMA,
    PARALLEL_PROVISION_ATTRIBUTES,
    PROVISION_ATTRIBUTES,
    ROOT_ATTRIBUTES,
)
from legalgraph.sources.model import Original, Source, SourceError, repo_path, sha256
from legalgraph.sources.render import NOTE_MARK, render_lines
from legalgraph.sources.text import comparable, original_text
from legalgraph.sources.translation_date import verify_translation_date
from legalgraph.sources.tree import (
    annotation,
    annotation_names,
    element_at,
    local,
    parents_of,
    provision_elements,
    provision_named,
    xpath,
)

WORDED_MEDIA = ("text/html", "application/pdf")  # other formats: the wording is compared by a reviewer


def verify_originals(source: Source) -> list[str]:
    errors = []
    for original in source.originals:
        if not original.file.exists():
            errors.append(f"{repo_path(original.file)}: missing; run `legalgraph sources fetch {source.id}`")
        elif sha256(original.file.read_bytes()) != original.sha256:
            errors.append(f"{repo_path(original.file)}: SHA-256 differs from source.yaml (originals are never edited)")
    return errors


def schema_errors(schema: etree.XMLSchema, data: bytes, where: str) -> list[str]:
    if schema.validate(etree.fromstring(data)):
        return []
    return [f"{where}:{entry.line}: {entry.message}" for entry in schema.error_log]


def unknown_annotations(root: ET.Element, where: str, allowed_below: set[str] | None = None) -> list[str]:
    """Annotations an element may not carry: the root has the act's, provisions theirs, items theirs.
    `allowed_below` replaces the provision and item sets (for authored translations)."""
    errors = []
    for element in root.iter():
        names = annotation_names(element)
        if element is root:
            allowed = ROOT_ATTRIBUTES
        elif allowed_below is not None:
            allowed = allowed_below
        else:
            allowed = PROVISION_ATTRIBUTES if "provision" in names else ITEM_ATTRIBUTES
        if unknown := names - allowed:
            errors.append(f"{where}: <{local(element.tag)}> has unknown annotation(s) {sorted(unknown)}")
    return errors


def words_occur(section: ET.Element, original: Original, haystacks: dict[str, str], where: str) -> list[str]:
    """Every paragraph of an authored section occurs word for word in its original. A PDF's page
    headers and footers can fall between two lines, so there each line (paragraph lead-in, numbered
    item) is compared on its own; elsewhere the paragraph."""
    if original.media_type not in WORDED_MEDIA:
        return []
    media = original.media_type
    haystack = haystacks.setdefault(original.file.name, comparable(original_text(original), media))
    errors = []
    for paragraph in section.iter(f"{{{LAW_NS}}}paragraph"):
        marked = "\n".join(line.text for line in render_lines(paragraph, marks=True))
        if media == "application/pdf":
            marked = marked.replace("\n", NOTE_MARK)
        if any(comparable(part, media) not in haystack for part in marked.split(NOTE_MARK)):
            errors.append(
                f"{where}: {section.get('num')} {paragraph.get('num', '')}: text does not occur word for "
                f"word in {original.file.name}"
            )
    return errors


def verify_official(source: Source, root: ET.Element, annotated: bytes, where: str) -> list[str]:
    errors = []
    if len(source.texts) != 1:
        errors.append(f"{repo_path(source.index)}: official-xml has exactly one original with role text")
    elif strip_annotations(annotated) != source.texts[0].file.read_bytes():
        errors.append(f"{where}: without its lga: attributes it is not byte-identical to the original")
    if any(original.annotated for original in source.parallels):
        errors.append(f"{repo_path(source.index)}: `annotated` on a parallel is for authored translations")
    errors += verify_parallels(source, root)
    errors += verify_consolidation(source, root) if source.authentic else verify_corrigenda(source, root)
    return errors


def verify_authored(source: Source, root: ET.Element, annotated: bytes, where: str) -> list[str]:
    schema = etree.XMLSchema(etree.parse(LAW_SCHEMA))
    errors = schema_errors(schema, annotated, where)
    haystacks: dict[str, str] = {}
    for section in root.iter(f"{{{LAW_NS}}}section"):
        errors += words_occur(section, source.original(section.get("source", "")), haystacks, where)
    return errors + verify_against_authentic(source, root, where) + verify_authored_parallels(source, root, schema)


def verify_against_authentic(source: Source, root: ET.Element, where: str) -> list[str]:
    """Sourcing and checking apart: every paragraph, wherever its words were taken from (a mirror),
    must also occur word for word in each authentic original of the source's language, the official
    publication downloaded or rendered by `sources fetch`."""
    authentic = [o for o in source.authentic if source.language_of(o) == source.language]
    errors: list[str] = []
    for original in authentic:
        haystacks: dict[str, str] = {}
        for section in root.iter(f"{{{LAW_NS}}}section"):
            errors += words_occur(section, original, haystacks, where)
    return errors


def verify(source: Source) -> list[str]:
    if errors := verify_originals(source):
        return errors
    annotated = source.annotated.read_bytes()
    where = repo_path(source.annotated)
    try:
        root = ET.fromstring(annotated)
    except ET.ParseError as error:
        return [f"{where}: {error}"]
    check = verify_official if source.kind == "official-xml" else verify_authored
    return check(source, root, annotated, where) + unknown_annotations(root, where)


def verify_parallels(source: Source, root: ET.Element) -> list[str]:
    """Each provision must be at the same place in every other language version, with the same
    identifiers and the same number of lines, so the versions can be read side by side."""
    errors = []
    parents = parents_of(root)
    for parallel in source.parallels:
        other = ET.fromstring(parallel.file.read_bytes())
        name = parallel.file.name
        for element in provision_elements(root):
            path = xpath(element, parents)
            match = element_at(other, path)
            label = annotation(element, "provision")
            if match is None or local(match.tag) != local(element.tag):
                errors.append(f"{name}: no <{local(element.tag)}> at {path} for {label}")
            elif match.get("IDENTIFIER") != element.get("IDENTIFIER") or match.get("eId") != element.get("eId"):
                errors.append(
                    f"{name}: {path} has IDENTIFIER {match.get('IDENTIFIER')!r}, not {element.get('IDENTIFIER')!r}"
                )
            elif (theirs := len(render_lines(match))) != (ours := len(render_lines(element))):
                errors.append(f"{name}: {label} has {theirs} lines, the annotated text {ours}")
    return errors


def translated_sections(source: Source, parallel: Original, p_root: ET.Element, where: str) -> list[str]:
    """The words of a translation's sections come from its own original."""
    errors = []
    haystacks: dict[str, str] = {}
    for section in p_root.iter(f"{{{LAW_NS}}}section"):
        try:
            original = source.original(section.get("source", ""))
        except SourceError:
            errors.append(f"{where}: section {section.get('num')}: unknown source {section.get('source')!r}")
            continue
        if original is not parallel:
            errors.append(
                f"{where}: section {section.get('num')}: its words must come from {parallel.file.name}, "
                f"not {original.file.name}"
            )
            continue
        errors += words_occur(section, original, haystacks, where)
    return errors


def translated_provisions(source: Source, root: ET.Element, p_root: ET.Element, where: str) -> list[str]:
    """Every provision a translation carries exists in the annotated text with as many lines."""
    errors = []
    for element in provision_elements(p_root):
        label = annotation(element, "provision")
        main = provision_named(root, label)
        if main is None:
            errors.append(f"{where}: {label}: no such provision in {repo_path(source.annotated)}")
        elif (theirs := len(render_lines(element))) != (ours := len(render_lines(main))):
            errors.append(f"{where}: {label} has {theirs} lines, the annotated text {ours}")
    return errors


def verify_authored_parallel(
    source: Source, root: ET.Element, parallel: Original, schema: etree.XMLSchema
) -> list[str]:
    if parallel.annotated is None:
        return [
            f"{repo_path(source.index)}: {parallel.file.name} is a parallel of an authored-xml "
            "source and needs `annotated`, its translation in schemas/law.xsd"
        ]
    where = repo_path(parallel.annotated)
    if not parallel.annotated.exists():
        return [f"{where}: missing"]
    data = parallel.annotated.read_bytes()
    try:
        p_root = ET.fromstring(data)
    except ET.ParseError as error:
        return [f"{where}: {error}"]
    errors = schema_errors(schema, data, where)
    errors += unknown_annotations(p_root, where, allowed_below=PARALLEL_PROVISION_ATTRIBUTES)
    errors += translated_sections(source, parallel, p_root, where)
    errors += translated_provisions(source, root, p_root, where)
    if parallel.as_of:
        errors += verify_translation_date(source, root, parallel, p_root)
    return errors


def verify_authored_parallels(source: Source, root: ET.Element, schema: etree.XMLSchema) -> list[str]:
    """The parallel language versions of an authored source are translations the maintainers write
    in schemas/law.xsd (e.g. the Rada's official English of a Ukrainian act): the parallel's
    `annotated` names that file. Its words are checked against its own original, every provision it
    carries must exist in the annotated text with the same number of lines (matched by
    lga:provision, not position), and lga:provision and lga:url are the only annotations allowed.
    A provision the translation does not carry simply gets no official English."""
    return [
        error for parallel in source.parallels for error in verify_authored_parallel(source, root, parallel, schema)
    ]
