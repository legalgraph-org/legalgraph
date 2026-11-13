"""Finding one's way in an annotated XML tree: annotations, provisions and paths between texts."""

import re
import xml.etree.ElementTree as ET

from legalgraph.sources.constants import ANNOTATION_NS
from legalgraph.sources.model import SourceError

Parents = dict[ET.Element, ET.Element]


def parents_of(root: ET.Element) -> Parents:
    return {child: parent for parent in root.iter() for child in parent}


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def annotation(element: ET.Element, name: str) -> str | None:
    return element.get(f"{{{ANNOTATION_NS}}}{name}")


def annotation_names(element: ET.Element) -> set[str]:
    prefix = f"{{{ANNOTATION_NS}}}"
    return {key.removeprefix(prefix) for key in element.attrib if key.startswith(prefix)}


def required(element: ET.Element, name: str, where: str) -> str:
    value = annotation(element, name)
    if not value:
        raise SourceError(f"{where}: <{local(element.tag)}> is missing lga:{name}")
    return value


def xpath(element: ET.Element, parents: Parents) -> str:
    steps = []
    while element in parents:
        parent = parents[element]
        same = [child for child in parent if child.tag == element.tag]
        steps.append(f"{local(element.tag)}[{same.index(element) + 1}]")
        element = parent
    steps.append(local(element.tag))
    return "/" + "/".join(reversed(steps))


def element_at(root: ET.Element, path: str) -> ET.Element | None:
    """The element at an XPath made by xpath() (/ROOT/CHILD[n]/…), or None."""
    steps = path.strip("/").split("/")
    if not steps or local(root.tag) != steps[0]:
        return None
    element = root
    for step in steps[1:]:
        match = re.fullmatch(r"([^\[]+)\[(\d+)\]", step)
        if not match:
            return None
        same = [child for child in element if local(child.tag) == match.group(1)]
        index = int(match.group(2)) - 1
        if index >= len(same):
            return None
        element = same[index]
    return element


def provision_elements(root: ET.Element) -> list[ET.Element]:
    return [element for element in root.iter() if element is not root and annotation(element, "provision")]


def provision_named(root: ET.Element, label: str | None) -> ET.Element | None:
    """The element annotated as the provision `label`, wherever it is."""
    return next((element for element in provision_elements(root) if annotation(element, "provision") == label), None)


def inside_provision(element: ET.Element, parents: Parents) -> bool:
    """The element is a provision or lies inside one."""
    if annotation(element, "provision"):
        return True
    while element in parents:
        element = parents[element]
        if annotation(element, "provision"):
            return True
    return False


def section_source(element: ET.Element, parents: Parents) -> str:
    while element in parents:
        element = parents[element]
        if local(element.tag) == "section":
            return element.get("source", "")
    raise SourceError("Provision outside a <section>")
