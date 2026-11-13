"""Cross-references inside an EU act, read mechanically from its English text ("point (f) of
Article 6(1)", "Articles 13 and 14", "paragraph 2"), to the act's own provisions."""

import re

REFERENCE = re.compile(
    r"\b(?:Articles? (?P<articles>\d+(?:\(\d+\))?(?:(?:, | and | or | to )\d+(?:\(\d+\))?)*)"
    r"|paragraphs? (?P<paragraphs>\d+(?:(?:, | and | or | to )\d+)*))"
    r"(?! of (?:the |this )?(?:Directive|Regulation|Decision|Charter|Treaty|TFEU|Council))"
)
SEPARATOR = re.compile(r", | and | or | to ")


def article_references(articles: str, act: str) -> list[str]:
    """Article N(M) is <act>-artN-M; "Articles 13 to 16" includes the articles in between."""
    parts = SEPARATOR.split(articles)
    numbers = [match for part in parts if (match := re.fullmatch(r"(\d+)(?:\((\d+)\))?", part))]
    found = [f"{act}-art{n.group(1)}" + (f"-{n.group(2)}" if n.group(2) else "") for n in numbers]
    if " to " in articles and len(parts) == 2 and all(part.isdigit() for part in parts):
        found += [f"{act}-art{n}" for n in range(int(parts[0]) + 1, int(parts[1]))]
    return found


def internal_references(text: str, act: str, own_article: str | None) -> list[str]:
    """Identifiers of the provisions an EU act's text points to within the same act: Article N(M) is
    <act>-artN-M, Article N any provision of article N, paragraph M of the provision's own article.
    References to other acts ("Article 8 of the Charter") are left out."""
    found: list[str] = []
    for match in REFERENCE.finditer(text):
        if match.group("articles"):
            found += article_references(match.group("articles"), act)
        elif own_article:
            found += [f"{act}-art{own_article}-{part}" for part in SEPARATOR.split(match.group("paragraphs"))]
    # "Article N" without a paragraph: every provision of the article; resolved by the caller's prefix match.
    return [target for ref in found for target in expand_article(ref)]


def expand_article(reference: str) -> list[str]:
    return (
        [reference]
        if re.search(r"-art\d+-\d+$", reference)
        else [reference, *(f"{reference}-{n}" for n in range(1, 30))]
    )
