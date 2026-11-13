"""The reading view of a source for the site: its annotated sections, paragraph by paragraph and line
by line, with their annotations, the section's XML and the same provisions in the other languages."""

import copy
import re
import xml.etree.ElementTree as ET

from lxml import etree

from legalgraph.sources.constants import LAW_NS, LINK_PREDICATES, PROVISION_ROLES
from legalgraph.sources.headings import heading
from legalgraph.sources.model import Original, Source
from legalgraph.sources.render import render, render_lines
from legalgraph.sources.tree import (
    Parents,
    annotation,
    annotation_names,
    element_at,
    local,
    parents_of,
    provision_named,
    xpath,
)

READING_ROLES = ("citation", *PROVISION_ROLES, *LINK_PREDICATES)

# Elements shown as one section of a reading page: a § (gesetze-im-internet.de, authored XML), an
# article or recital (Formex), a regulation or section (legislation.gov.uk), a CFR section (eCFR), the
# operative part or a group of grounds of a judgment. A provision's section is its nearest one.
CONTAINERS = {
    "norm", "section", "ARTICLE", "article", "CONSID", "ANNEX", "CONS.ANNEX", "P1", "Schedule", "DIV8", "SECTION",
    "JURISDICTION", "GR.SEQ",
}  # fmt: skip
HEADINGS = {
    "Number", "TitleBlock", "Reference", "TI.ART", "STI.ART", "Pnumber", "Title", "HEAD", "INTRO", "TITLE",
    "metadaten", "SECTNO", "SUBJECT", "num", "heading",
}  # fmt: skip

Parallel = tuple[Original, str, ET.Element]  # an original, its language and its parsed text


def has_annotations(element: ET.Element) -> bool:
    return any(annotation_names(node) for node in element.iter())


def formatted_xml(annotated: bytes, path: str) -> str:
    """The element at `path` (an XPath from xpath()) as indented XML, for reading, with the file's own
    namespace prefixes. The file itself is never reformatted."""
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    document = etree.fromstring(annotated, parser)
    steps = [re.fullmatch(r"([^\[]+)(\[\d+\])?", step) for step in path.strip("/").split("/")]
    expression = "/" + "/".join(f"*[local-name()='{m.group(1)}']{m.group(2) or ''}" for m in steps if m)
    element = copy.deepcopy(document.xpath(expression)[0])
    etree.indent(element, space="  ")
    return etree.tostring(element, encoding="unicode", pretty_print=True).rstrip()


def nested_provision(child: ET.Element) -> bool:
    """A provision lies deeper inside the element than the element itself."""
    nested = any(annotation(node, "provision") for node in child.iter() if node is not child)
    return nested and not annotation(child, "provision")


def norm_units(container: ET.Element) -> list[ET.Element]:
    content = container.find("textdaten/text/Content")
    units: list[ET.Element] = []
    for child in content if content is not None else []:
        if nested_provision(child):  # a provision on a numbered item (UWG Anhang)
            outer = next(child.iter("DL"), None)  # its outermost list: numbers and items in turn
            units += list(outer) if outer is not None else [child]
        else:
            units.append(child)
    return units


def reading_units(container: ET.Element) -> list[ET.Element]:
    """The parts of a section shown one by one: its paragraphs, or, where provisions sit deeper (the
    numbered definitions of Article 4 GDPR, the points of a ruling), each of them on its own."""
    if annotation(container, "provision"):
        return [container]
    if local(container.tag) == "norm":
        return norm_units(container)
    if container.tag == f"{{{LAW_NS}}}section":
        return container.findall(f"{{{LAW_NS}}}paragraph")
    units = []
    for child in container:
        if local(child.tag) in HEADINGS:
            continue
        units += reading_units(child) if nested_provision(child) else [child]
    return units


def containing_section(element: ET.Element, parents: Parents) -> ET.Element | None:
    node: ET.Element | None = element
    while node is not None:
        if local(node.tag) in CONTAINERS:
            return node
        node = parents.get(node)
    return None


def annotated_sections(root: ET.Element, parents: Parents) -> list[ET.Element]:
    containers: list[ET.Element] = []
    for element in root.iter():
        if element is not root and annotation_names(element):
            container = containing_section(element, parents)
            if container is not None and container not in containers:
                containers.append(container)
    return containers


def versions(element: ET.Element, parents: Parents, parallels: list[Parallel]) -> dict[str, list[str]]:
    """The provision's lines in each parallel language version that has it."""
    found = {}
    for original, language, other in parallels:
        if original.annotated is not None:  # an authored translation: same provision, anywhere
            match = provision_named(other, annotation(element, "provision"))
        else:
            match = element_at(other, xpath(element, parents))
        if match is not None:
            found[language] = [line.text for line in render_lines(match)]
    return found


def section_titles(container: ET.Element, parents: Parents, parallels: list[Parallel]) -> dict[str, str]:
    titles = {}
    for _original, language, other in parallels:
        match = element_at(other, xpath(container, parents))
        if match is not None and local(match.tag) == "ARTICLE" and (found := match.find("STI.ART")) is not None:
            titles[language] = render(found)
    return titles


def paragraph_view(paragraph: ET.Element, parents: Parents, parallels: list[Parallel]) -> dict[str, object]:
    provision = annotation(paragraph, "provision")
    return {
        "xpath": xpath(paragraph, parents),
        "provision": provision,
        "annotations": {role: value for role in READING_ROLES if (value := annotation(paragraph, role))},
        "lines": [
            {"text": line.text, "requires": line.requires, "defines": line.defines} for line in render_lines(paragraph)
        ],
        "versions": versions(paragraph, parents, parallels) if provision else {},
    }


def reading_view(source: Source) -> list[dict[str, object]]:
    """The annotated sections of a source (a § or article each). Unannotated sections are left out.
    Provisions carry the same lines in each parallel language version."""
    annotated = source.annotated.read_bytes()
    root = ET.fromstring(annotated)
    parents = parents_of(root)
    parallels = [
        (original, source.language_of(original), ET.fromstring((original.annotated or original.file).read_bytes()))
        for original in source.parallels
    ]
    sections = []
    for container in annotated_sections(root, parents):
        number, title = heading(container, parents)
        is_section = container.tag == f"{{{LAW_NS}}}section"
        file_name = container.get("source") if is_section else source.texts[0].file.name
        path = xpath(container, parents)
        sections.append(
            {
                "num": number,
                "title": title,
                "titles": section_titles(container, parents, parallels),
                "source": file_name or "",
                "xpath": path,
                "xml": formatted_xml(annotated, path),
                "paragraphs": [
                    paragraph_view(paragraph, parents, parallels)
                    for paragraph in reading_units(container)
                    if render_lines(paragraph)  # an empty element (a bare list wrapper) shows nothing
                ],
            }
        )
    return sections
