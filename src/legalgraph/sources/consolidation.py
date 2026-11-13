"""Checks that an EU text quoted from the Official Journal or a consolidated version reads as the law
does: corrigenda applied, and every difference to the authentic text explained."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from legalgraph.sources.formex import changed_places, covers, find_by_key, formex_key, formex_place
from legalgraph.sources.model import Original, Source, repo_path
from legalgraph.sources.render import render, render_lines
from legalgraph.sources.text import authentic_form, collapse, original_text, plain_quotes, trim
from legalgraph.sources.tree import Parents, annotation, element_at, parents_of, provision_elements, xpath


def verify_corrigenda(source: Source, root: ET.Element) -> list[str]:
    """When the annotated text is the Official Journal text itself, a corrigendum that corrects an
    annotated provision must be applied first. `corrects` in source.yaml lists the places each
    corrigendum changes (Art. 4(18), Recital 71, …)."""
    errors = []
    parents = parents_of(root)
    for corrigendum in source.corrigenda:
        for place, change in zip(corrigendum.corrects, changed_places(corrigendum), strict=False):
            for element in provision_elements(root):
                found = formex_place(element, parents)
                if found and covers(change, found):
                    errors.append(
                        f"{corrigendum.file.name} corrects {place}, which {annotation(element, 'provision')} quotes"
                    )
    return errors


@dataclass
class Authentic:
    """The authentic text a consolidated one is compared with, in one language: Formex where the
    Official Journal has it (from 2004), else its HTML or PDF."""

    original: Original
    changes: list[Original]  # corrigenda and amending acts in the same language
    haystack: str = ""  # an HTML or PDF text, as compared
    tree: ET.Element | None = None  # a Formex text

    @classmethod
    def of(cls, original: Original, changes: list[Original]) -> Authentic:
        media = original.media_type
        if media in ("application/pdf", "text/html"):
            return cls(original, changes, haystack=authentic_form(original_text(original), media))
        return cls(original, changes, tree=ET.fromstring(original.file.read_bytes()))

    def unchanged_lines(self, current: ET.Element, parents: Parents) -> set[str]:
        """The lines of the element that read as in the authentic text, final punctuation aside: a
        list's last point becomes a middle one when an amendment adds a point after it."""
        media = self.original.media_type
        if self.tree is None:
            lines = render_lines(current)
            return {trim(line.text) for line in lines if authentic_form(trim(line.text), media) in self.haystack}
        before = find_by_key(self.tree, formex_key(current, parents))
        return {trim(line.text) for line in render_lines(before)} if before is not None else set()


def amended_lines_found(changed: list[str], amendments: list[Original], label: str | None, name: str) -> list[str]:
    """Each changed line must occur word for word in an amending act. Quoted there, the text's own
    quotation marks become inner ones (‘…’ turns into “…”), so quotation marks are compared as one
    character, and the final punctuation of a list point differs as against the authentic text."""
    bodies = [plain_quotes(collapse(render(ET.fromstring(o.file.read_bytes())))) for o in amendments]
    names = ", ".join(o.file.name for o in amendments)
    return [
        f"{name}: {label}: “{line[:60]}…” does not occur word for word in {names}"
        for line in changed
        if not any(plain_quotes(collapse(trim(line))) in body for body in bodies)
    ]


def verify_version(source: Source, root: ET.Element, original: Original, tree: ET.Element) -> list[str]:
    """One language version of a consolidated text against the authentic text in its language."""
    language = source.language_of(original)
    authentic = [o for o in source.authentic if source.language_of(o) == language]
    if not authentic:
        return [f"{repo_path(source.index)}: no authentic text in {language} for {original.file.name}"]
    changes = [o for o in source.corrigenda + source.amendments if source.language_of(o) == language]
    reference = Authentic.of(authentic[0], changes)
    parents, tree_parents = parents_of(root), parents_of(tree)
    errors = []
    for element in provision_elements(root):
        label = annotation(element, "provision")
        current = element if tree is root else element_at(tree, xpath(element, parents))
        if current is None:
            continue  # reported by verify_parallels
        unchanged = reference.unchanged_lines(current, tree_parents)
        changed = [line.text for line in render_lines(current) if trim(line.text) not in unchanged]
        if not changed:
            continue
        place = formex_place(element, parents)
        explained = [o for o in reference.changes if place and any(covers(c, place) for c in changed_places(o))]
        if not explained:
            errors.append(
                f"{original.file.name}: {label} differs from the authentic text {reference.original.file.name} "
                "and no corrigendum or amending act in source.yaml lists its place"
            )
            continue
        amendments = [o for o in explained if o.role == "amendment"]
        if amendments and not any(o.role == "corrigendum" for o in explained):
            errors += amended_lines_found(changed, amendments, label, original.file.name)
    return errors


def verify_consolidation(source: Source, root: ET.Element) -> list[str]:
    """A consolidated text (the act with its corrigenda and amendments worked in, which the
    Publications Office publishes as a documentation tool) is checked against the authentic texts:
    every line of a quoted provision (a subparagraph or point) must read exactly as in the Official
    Journal publication of the act (role: authentic), unless a corrigendum or amending act of the same
    language lists its place; a line an amending act changed must occur word for word in that act."""
    versions = [(source.texts[0], root)] + [(o, ET.fromstring(o.file.read_bytes())) for o in source.parallels]
    return [error for original, tree in versions for error in verify_version(source, root, original, tree)]
