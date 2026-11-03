import re
from dataclasses import dataclass, field

import notes
from db import match
from models import TYPE_PLURAL, TYPE_SINGULAR, EventType, Subject, SubjectEdit

COMMAND = "/setup"
ALIAS_KEY = "shortcut"
SUBJECT_KEY = "all"

_HEADER_RE = re.compile(r"\[\s*(?P<query>[^\]]+?)\s*\]")
_LINE_RE = re.compile(r"(?P<key>[^:]+?)\s*:(?P<value>.*)")

_SCOPES: dict[str, EventType | None] = {SUBJECT_KEY: None} | {
    name.casefold(): t for t in EventType for name in (t.value, TYPE_SINGULAR[t], TYPE_PLURAL[t])
}


@dataclass
class SetupError:
    line: int
    message: str


@dataclass
class Block:
    line: int
    query: str
    alias_line: int = 0
    alias: str | None = None
    lines: dict[EventType | None, list[str]] = field(default_factory=dict)
    scope_lines: dict[EventType | None, int] = field(default_factory=dict)


def parse(text: str) -> tuple[list[Block], list[SetupError]]:
    blocks: list[Block] = []
    errors: list[SetupError] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if header := _HEADER_RE.fullmatch(line):
            blocks.append(Block(number, header["query"]))
            continue
        if not blocks:
            errors.append(SetupError(number, "Start with a subject line, like [manazment]"))
            continue
        m = _LINE_RE.fullmatch(line)
        key = m["key"].casefold() if m else ""
        if m is None or (key != ALIAS_KEY and key not in _SCOPES):
            errors.append(SetupError(number, f"Expected {ALIAS_KEY}, {SUBJECT_KEY} or a type "
                                             "(P, CV, S, EXAM) before a colon"))
            continue
        block, value = blocks[-1], m["value"].strip()
        if key == ALIAS_KEY:
            if block.alias_line:
                errors.append(SetupError(number, "The shortcut is set twice"))
                continue
            block.alias_line = number
            try:
                block.alias = notes.normalize_alias(value) if value else None
            except notes.NoteError as e:
                errors.append(SetupError(number, str(e)))
            continue
        scope = _SCOPES[key]
        block.scope_lines.setdefault(scope, number)
        block.lines.setdefault(scope, []).append(value)
    return blocks, errors


def _note(block: Block, scope: EventType | None, errors: list[SetupError]) -> str | None:
    body = "\n".join(line for line in block.lines[scope] if line)
    if not body:
        return None
    try:
        return notes.normalize(body)
    except notes.NoteError as e:
        errors.append(SetupError(block.scope_lines[scope], str(e)))
        return None


def _scope_label(scope: EventType | None) -> str:
    return "whole subject" if scope is None else TYPE_PLURAL[scope].lower()


def resolve(blocks: list[Block], subjects: list[Subject]
            ) -> tuple[dict[int, SubjectEdit], dict[int, list[str]], list[SetupError]]:
    edits: dict[int, SubjectEdit] = {}
    changes: dict[int, list[str]] = {}
    errors: list[SetupError] = []
    claimed: dict[int, Block] = {}
    for block in blocks:
        found = match(subjects, block.query)
        if len(found) != 1:
            errors.append(SetupError(block.line, f"No subject matches \"{block.query}\"" if not found
                                     else f"\"{block.query}\" matches " + ", ".join(s.name for s in found)))
            continue
        subject = found[0]
        if subject.id in claimed:
            errors.append(SetupError(block.line, f"{subject.name} is listed twice"))
            continue
        claimed[subject.id] = block

        edit, changed = SubjectEdit(), []
        if block.alias_line and block.alias != subject.alias:
            edit.sets_alias, edit.alias = True, block.alias
            changed.append(ALIAS_KEY)
        for scope, line in block.scope_lines.items():
            if scope is not None and scope not in subject.types:
                errors.append(SetupError(line, f"{subject.name} has no "
                                               f"{TYPE_PLURAL[scope].lower()} in the timetable"))
                continue
            note = _note(block, scope, errors)
            current = subject.note if scope is None else subject.series_notes.get(scope)
            if note != current:
                edit.notes[scope] = note
                changed.append(_scope_label(scope))
        if changed:
            edits[subject.id], changes[subject.id] = edit, changed

    owners: dict[str, list[Subject]] = {}
    for s in subjects:
        alias = edits[s.id].alias if s.id in edits and edits[s.id].sets_alias else s.alias
        if alias:
            owners.setdefault(alias.casefold(), []).append(s)
    for clash in (group for group in owners.values() if len(group) > 1):
        for s in clash:
            if s.id in claimed and claimed[s.id].alias_line:
                errors.append(SetupError(claimed[s.id].alias_line, "This shortcut is also on "
                                         + ", ".join(o.name for o in clash if o is not s)))
    return edits, changes, errors


def _note_lines(key: str, note: str | None) -> list[str]:
    return [f"{key}: {line}" for line in note.splitlines()] if note else [f"{key}:"]


def render(subjects: list[Subject]) -> str:
    out = [COMMAND]
    for s in subjects:
        out += ["", f"[{s.name}]", f"{ALIAS_KEY}: {s.alias or ''}".rstrip()]
        out += _note_lines(SUBJECT_KEY, s.note)
        for t in s.types:
            out += _note_lines(t.value, s.series_notes.get(t))
    return "\n".join(out)
