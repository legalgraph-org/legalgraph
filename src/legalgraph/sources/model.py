"""A source: one act's directory under sources/, read from its source.yaml index.

The index is validated by pydantic models that mirror the YAML exactly, so a typo or a wrong value
fails with the field it is in; the dataclasses below are what the rest of the code works with.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from legalgraph.load import REPO_ROOT
from legalgraph.sources.constants import EXTRACTED_DIR, LICENCES, SOURCES_DIR


class SourceError(Exception):
    pass


Role = Literal["text", "parallel", "authentic", "amendment", "corrigendum"]


@dataclass
class Original:
    file: Path
    url: str
    fetch: str
    media_type: str
    retrieved_on: date
    sha256: str
    member: str | None = None
    selector: str | None = None
    wait: str | None = None  # rendered: the element to wait for before cutting the fragment
    text_ignore: list[str] = field(default_factory=list)
    # A PDF whose fonts carry no Unicode map: the codec of the bytes it shows (old Greek ΦΕΚ: cp1253).
    pdf_encoding: str | None = None
    # False for a mirror's copy: its words count as the law's once verified against an authentic original.
    official: bool = True
    headers: dict[str, str] = field(default_factory=dict)
    role: str = "text"
    language: str | None = None
    title: str | None = None
    corrects: list[str] = field(default_factory=list)
    page: str | None = None
    notes: list[str] = field(default_factory=list)
    authentic: bool = True  # False for a translation published for information (a judgment outside its case language)
    pause: float = 0  # seconds to wait before downloading, for portals that block quick successive requests
    annotated: Path | None = None  # authored-xml parallel: its own XML written in schemas/law.xsd
    as_of: date | None = None  # the translation's date: amendment notes newer than this make it stale


@dataclass
class Source:
    index: Path
    id: str
    title: str
    jurisdiction: str
    language: str
    kind: str
    originals: list[Original]
    annotated: Path
    document: str | None = None  # identifier of the source document, when <act>-source is taken
    licence: str | None = None  # a key of LICENCES
    licence_basis: str | None = None  # why it applies

    @property
    def directory(self) -> Path:
        return self.index.parent

    @property
    def output(self) -> Path:
        return EXTRACTED_DIR / f"{self.id}.ttl"

    def with_role(self, role: Role) -> list[Original]:
        return [original for original in self.originals if original.role == role]

    @property
    def texts(self) -> list[Original]:
        return self.with_role("text")

    @property
    def parallels(self) -> list[Original]:
        return self.with_role("parallel")

    @property
    def corrigenda(self) -> list[Original]:
        return self.with_role("corrigendum")

    @property
    def authentic(self) -> list[Original]:
        return self.with_role("authentic")

    @property
    def amendments(self) -> list[Original]:
        return self.with_role("amendment")

    def language_of(self, original: Original) -> str:
        return original.language or self.language

    def original(self, name: str) -> Original:
        for original in self.originals:
            if original.file.name == name:
                return original
        raise SourceError(f"{repo_path(self.index)}: no original named {name!r}")


# --- The index as written ------------------------------------------------------


class OriginalEntry(BaseModel):
    """One entry of `originals:` in source.yaml."""

    model_config = ConfigDict(extra="forbid")

    file: str
    url: str
    fetch: Literal["zip-member", "html-fragment", "rendered", "file"]
    media_type: str
    retrieved_on: date
    sha256: str
    member: str | None = None
    selector: str | None = None
    wait: str | None = None  # rendered: the element to wait for before cutting the fragment
    text_ignore: list[str] = Field(default_factory=list)
    pdf_encoding: str | None = None
    official: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    role: Role = "text"
    language: str | None = None
    title: str | None = None
    corrects: list[str] = Field(default_factory=list)
    amends: list[str] = Field(default_factory=list)  # the places an amending act changes, as `corrects`
    page: str | None = None
    notes: list[str] = Field(default_factory=list)
    authentic: bool = True
    pause: float = 0
    annotated: str | None = None
    as_of: date | None = None

    @field_validator("sha256", mode="before")
    @classmethod
    def hash_text(cls, value: object) -> str:
        return str(value)  # YAML reads a hash of digits only as a number

    @model_validator(mode="after")
    def parallel_only(self) -> OriginalEntry:
        if (self.annotated or self.as_of) and self.role != "parallel":
            raise ValueError("`annotated` and `as_of` are for parallel language versions")
        return self

    def original(self, directory: Path) -> Original:
        return Original(
            file=(directory / self.file).resolve(),
            url=self.url,
            fetch=self.fetch,
            media_type=self.media_type,
            retrieved_on=self.retrieved_on,
            sha256=self.sha256,
            member=self.member,
            selector=self.selector,
            wait=self.wait,
            text_ignore=self.text_ignore,
            pdf_encoding=self.pdf_encoding,
            official=self.official,
            headers=self.headers,
            role=self.role,
            language=self.language,
            title=self.title,
            corrects=self.corrects or self.amends,
            page=self.page,
            notes=self.notes,
            authentic=self.authentic,
            pause=self.pause,
            annotated=(directory / self.annotated).resolve() if self.annotated else None,
            as_of=self.as_of,
        )


class SourceIndex(BaseModel):
    """A source.yaml file."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    jurisdiction: str
    language: str
    publisher: str | None = None
    kind: Literal["official-xml", "authored-xml"]
    licence: str | None = None
    licence_basis: str | None = None
    authentic: str | None = None  # the language of the authentic text, where the kept one is a translation
    document: str | None = None
    annotated: str
    originals: list[OriginalEntry]

    @model_validator(mode="after")
    def known_licence(self) -> SourceIndex:
        if self.licence is not None and self.licence not in LICENCES:
            raise ValueError(f"licence must be one of {sorted(LICENCES)}")
        if self.licence is not None and not self.licence_basis:
            raise ValueError("give `licence_basis` with `licence`")
        return self

    def source(self, index: Path) -> Source:
        return Source(
            index=index,
            id=self.id,
            title=self.title,
            jurisdiction=self.jurisdiction,
            language=self.language,
            kind=self.kind,
            originals=[entry.original(index.parent) for entry in self.originals],
            annotated=index.parent / self.annotated,
            document=self.document,
            licence=self.licence,
            licence_basis=self.licence_basis,
        )


def validation_message(error: ValidationError) -> str:
    """Pydantic's errors as one line each: where in the file, and what is wrong."""
    lines = []
    for problem in error.errors():
        where = ".".join(str(part) for part in problem["loc"])
        message = problem["msg"].removeprefix("Value error, ")
        lines.append(f"{where}: {message}" if where else message)
    return "; ".join(lines)


def parse_index(index: Path) -> Source:
    try:
        return SourceIndex.model_validate(yaml.safe_load(index.read_text())).source(index)
    except ValidationError as error:
        raise SourceError(f"{repo_path(index)}: {validation_message(error)}") from error


def load_sources(root: Path = SOURCES_DIR, ids: tuple[str, ...] = ()) -> list[Source]:
    sources = [parse_index(index) for index in sorted(root.rglob("source.yaml"))]
    if ids:
        unknown = set(ids) - {source.id for source in sources}
        if unknown:
            raise SourceError(f"Unknown source(s): {', '.join(sorted(unknown))}")
        sources = [source for source in sources if source.id in ids]
    return sources


def repo_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else str(path)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
