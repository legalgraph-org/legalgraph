"""One entry of a gettext PO file: its comments, msgctxt, msgid and msgstr, kept as the file wrote them."""

FIELDS = ("msgctxt", "msgid", "msgstr")


def quoted(line: str) -> str:
    """The text between the first quote and the last unescaped quote of a line, or ""."""
    start = line.find('"')
    if start == -1:
        return ""
    end = len(line) - 1
    while end > start:
        if line[end] == '"' and line[end - 1] != "\\":
            return line[start + 1 : end]
        end -= 1
    return ""


class PoEntry:
    """A PO entry parsed from its raw lines, which are kept verbatim so the file can be written back
    unchanged. An entry marked with #~ is obsolete."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.msgid: str | None = None
        self.msgstr: str | None = None
        self.msgctxt: str | None = None
        self.msgstr_index = -1  # line index within self.lines where msgstr starts
        self.is_obsolete = False
        self._parse()

    def _parse(self) -> None:
        """Read msgctxt, msgid and msgstr, joining continuation lines ("…") to the field before."""
        current: str | None = None
        for index, line in enumerate(self.lines):
            stripped = line.strip()
            if stripped.startswith("#~"):
                self.is_obsolete = True
                stripped = stripped[2:].strip()
            field = next((name for name in FIELDS if stripped.startswith(name)), None)
            if field is not None:
                current = field
                setattr(self, field, quoted(stripped))
                if field == "msgstr":
                    self.msgstr_index = index
            elif stripped.startswith('"') and current is not None:
                setattr(self, current, getattr(self, current) + quoted(stripped))

    def is_translated(self) -> bool:
        return self.msgstr is not None and self.msgstr != ""

    def get_key(self) -> tuple[str | None, str | None]:
        """(msgctxt, msgid): what identifies a translation entry in a PO file."""
        return (self.msgctxt, self.msgid)

    def update_translation(self, new_translation: str) -> None:
        """Replace the msgstr lines with one line holding the new translation, keeping the indentation."""
        if self.msgstr_index == -1:
            return
        prefix = self.lines[self.msgstr_index].split("msgstr")[0]
        end = self.msgstr_index + 1
        while end < len(self.lines) and self.lines[end].strip().startswith('"'):
            end += 1
        self.lines[self.msgstr_index : end] = [f'{prefix}msgstr "{new_translation}"\n']
        self.msgstr = new_translation
