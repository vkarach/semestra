import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

MAX_LEN = 1000

_FIELD_RE = re.compile(r"(?P<key>[^\W\d_][^:/\n]{0,31}?)\s*:\s*(?P<value>\S.*)")


class NoteError(ValueError):
    pass


@dataclass
class ParsedNote:
    fields: dict[str, tuple[str, str]] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)

    def items(self) -> list[tuple[str, str]]:
        return list(self.fields.values())

    def links(self) -> list[tuple[str, str]]:
        named = [(k, v) for k, v in self.items() if is_url(v)]
        bare = [(urlsplit(line).hostname or line, line) for line in self.lines if is_url(line)]
        return named + bare

    def __bool__(self) -> bool:
        return bool(self.fields or self.lines)


def is_url(value: str) -> bool:
    if any(c.isspace() for c in value):
        return False
    parts = urlsplit(value)
    return parts.scheme in ("http", "https") and "." in (parts.hostname or "")


def _from_json(text: str) -> list[str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise NoteError(f"Looks like JSON but does not parse: {e.msg}, line {e.lineno}") from e
    if not isinstance(data, dict):
        raise NoteError("JSON note has to be an object, like {\"isi\": \"https://...\"}")
    return [f"{k}: {v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)}"
            for k, v in data.items()]


def _clean_line(line: str) -> str:
    line = line.strip().rstrip(",;").strip()
    m = _FIELD_RE.fullmatch(line)
    if m and not m["value"].startswith("//"):
        return f"{m['key'].strip()}: {m['value'].strip()}"
    return line


def normalize(text: str) -> str:
    text = text.strip()
    raw_lines = _from_json(text) if text.startswith("{") else text.splitlines()
    lines = [cleaned for line in raw_lines if (cleaned := _clean_line(line))]
    if not lines:
        raise NoteError("The note is empty")
    result = "\n".join(lines)
    if len(result) > MAX_LEN:
        raise NoteError(f"Too long: {len(result)} characters, the limit is {MAX_LEN}")
    return result


def parse(text: str | None) -> ParsedNote:
    note = ParsedNote()
    for line in (text or "").splitlines():
        m = _FIELD_RE.fullmatch(line)
        if m and not m["value"].startswith("//"):
            key = m["key"].strip()
            note.fields[key.casefold()] = (key, m["value"].strip())
        elif line.strip():
            note.lines.append(line.strip())
    return note


def merge(*texts: str | None) -> ParsedNote:
    merged = ParsedNote()
    for text in texts:
        part = parse(text)
        merged.fields.update(part.fields)
        merged.lines.extend(part.lines)
    return merged
