import logging
import sqlite3
import unicodedata

from models import EventType, Subject

log = logging.getLogger(__name__)


class AliasTaken(Exception):
    pass


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


class SubjectRepo:
    _LIST = (
        "SELECT j.id, j.name, j.alias, j.note FROM subjects j "
        "WHERE j.user_id = ? AND EXISTS "
        "(SELECT 1 FROM events e WHERE e.user_id = j.user_id AND e.name = j.name)"
    )
    _TYPES = "SELECT DISTINCT name, type FROM events WHERE user_id = ?"
    _SERIES = (
        "SELECT s.subject_id, s.type, s.note FROM series_notes s "
        "JOIN subjects j ON j.id = s.subject_id WHERE j.user_id = ?"
    )
    _SET_ALIAS = "UPDATE subjects SET alias = ? WHERE id = ? AND user_id = ?"
    _SET_NOTE = "UPDATE subjects SET note = ? WHERE id = ? AND user_id = ?"
    _UPSERT_SERIES = (
        "INSERT INTO series_notes (subject_id, type, note) "
        "SELECT id, ?, ? FROM subjects WHERE id = ? AND user_id = ? "
        "ON CONFLICT (subject_id, type) DO UPDATE SET note = excluded.note"
    )
    _DELETE_SERIES = (
        "DELETE FROM series_notes WHERE type = ? AND subject_id = "
        "(SELECT id FROM subjects WHERE id = ? AND user_id = ?)"
    )

    def __init__(self, conn):
        self._conn = conn


    async def list_subjects(self, user_id: int) -> list[Subject]:
        async with self._conn.execute(self._LIST, (user_id,)) as cursor:
            rows = await cursor.fetchall()
        async with self._conn.execute(self._TYPES, (user_id,)) as cursor:
            types: dict[str, list[EventType]] = {}
            for name, type_name in await cursor.fetchall():
                types.setdefault(name, []).append(EventType[type_name])
        async with self._conn.execute(self._SERIES, (user_id,)) as cursor:
            series: dict[int, dict[EventType, str]] = {}
            for subject_id, type_name, note in await cursor.fetchall():
                series.setdefault(subject_id, {})[EventType[type_name]] = note

        order = list(EventType)
        subjects = [
            Subject(id=r[0], name=r[1], alias=r[2], note=r[3],
                    series_notes=series.get(r[0], {}),
                    types=sorted(types.get(r[1], []), key=order.index))
            for r in rows
        ]
        return sorted(subjects, key=lambda s: fold(s.title))


    async def get_subject(self, user_id: int, subject_id: int) -> Subject | None:
        return next((s for s in await self.list_subjects(user_id) if s.id == subject_id), None)


    async def find(self, user_id: int, query: str) -> list[Subject]:
        q = fold(query.strip())
        subjects = await self.list_subjects(user_id)
        exact = [s for s in subjects if s.alias and fold(s.alias) == q]
        if exact:
            return exact
        return [s for s in subjects
                if q in fold(s.name) or (s.alias and q in fold(s.alias))]


    async def set_alias(self, user_id: int, subject_id: int, alias: str | None):
        try:
            await self._conn.execute(self._SET_ALIAS, (alias, subject_id, user_id))
        except sqlite3.IntegrityError as e:
            await self._conn.rollback()
            raise AliasTaken(alias) from e
        await self._conn.commit()


    async def set_note(self, user_id: int, subject_id: int, note: str | None):
        await self._conn.execute(self._SET_NOTE, (note, subject_id, user_id))
        await self._conn.commit()


    async def set_series_note(self, user_id: int, subject_id: int, event_type: EventType,
                              note: str | None):
        if note is None:
            await self._conn.execute(self._DELETE_SERIES, (event_type.name, subject_id, user_id))
        else:
            await self._conn.execute(self._UPSERT_SERIES,
                                     (event_type.name, note, subject_id, user_id))
        await self._conn.commit()
