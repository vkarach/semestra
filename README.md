# Semestra

Telegram bot that keeps a university timetable and reminds you before a class
starts. You export the timetable once as an `.ics` file and the bot answers
questions about it from then on.

## Importing

`/add_events` takes an `.ics` export, or you can send the file first and the bot
asks what to do with it. The file has to be `.ics` and under 5 MB.

Two modes, and the difference only matters once a timetable is already stored:

- **Replace** throws away everything from the previous import.
- **Merge** keeps the past and replaces only what is still ahead. A timetable
  reissued mid-semester changes the rest of the term, not the weeks already
  taught, so merging keeps the record of what actually happened.

Each import is tagged with its own id, and what the new file does not carry is
deleted by that tag rather than by matching events one by one. An event that
appears in both imports keeps its row, so a reminder already sent is not sent
again after a re-import.

`/ics_help` explains where the file comes from. At TUKE it is MAIS, under
**Rozvrh** -> **iCal export**.

## Time

The timezone is read from the file, not asked for: `X-WR-TIMEZONE` first, then
the `TZID` on the first event that carries one. A file that names a zone Python
cannot resolve is treated as if it named none, and the import still completes,
with a warning that the timezone could not be detected.

Weekly repeats are expanded at import time into one row per occurrence, because
a schedule query should be a range scan and not a recurrence calculation. Only
`FREQ=WEEKLY` with an `UNTIL` is expanded; anything else is kept as the single
occurrence it started as, and says so in the log.

## Asking

- `/next` - the next event
- `/today`, `/tomorrow` - one day, with buttons to step to the previous or next
  day and a button per event that opens its card
- `/week` - the current week
- `/schedule` - the next 7 days, starting from the next event rather than from
  today, so a request made on a free Saturday still shows a full week
- `/exams` - every assessment still ahead, with a countdown

An empty answer names the closest event instead of saying nothing.

## Subjects, shortcuts and notes

`/subjects` lists every subject in the timetable, `/subjects ux` opens one by
shortcut or by any part of its name, accents optional (`formalne` finds
`Formalne jazyky`). A subject can carry a shortcut, used instead of the full
name everywhere except its own card, so `Pouzivatelske rozhrania a pouzivatelsky
zazitok` reads as `UX`. Shortcuts are unique per user, case-insensitively.

Notes live on three levels, from widest to narrowest:

- **Subject** - every class of it (ISI page, teacher's contact).
- **Series** - one type of it, all lectures or all labs (the lecture's Webex).
- **Class** - one occurrence ("test today").

A card shows them merged into one list; when two levels set the same key, the
narrower one wins. Listings show only the class note, the card and the
reminders show everything.

A note is one `key: value` per line, a trailing comma or semicolon is dropped,
and a line without a key stays plain text. A JSON object is accepted and stored
as the same lines. Values and bare lines that are `http(s)` links with a real
host become link buttons on the card and on reminders. If Telegram still
rejects a link, the message goes out without the link buttons instead of not
at all.

`/setup` does all of this in one message. Sent alone it answers with the current
setup as text, one block per subject, ready to copy, edit and send back:

```
/setup
[manazment]
shortcut: MSP
all: isi: https://isi.tuke.sk/...
P: webex: https://tuke.webex.com/...
CV: teams: https://teams.microsoft.com/...
```

A block starts with the subject in brackets, found the same way as by
`/subjects`, and must match exactly one. Each line under it is a scope, a colon
and one line of the note: `shortcut`, `all` for the whole subject, or a type
(`P`, `CV`, `S`, `EXAM`, or `lectures`, `labs` and so on). Repeating a scope adds
lines to the same note, an empty scope clears it, and a scope left out is not
touched. The message is checked as a whole first: any bad line is reported with
its number and nothing is saved, so a half-applied setup cannot happen. Shortcuts
are cleared before they are set, which lets two subjects swap theirs in one go.

Subjects are rows of their own, created on import and kept when a subject drops
out of a timetable, so a shortcut and its notes come back with the subject next
semester. Class notes and the cancelled flag sit on the event row, which an
import keeps when the same event comes back.

## Event cards

Every listed event opens a card: where it is, the info line from the file, the
merged notes, and buttons to edit the class or series note, open the subject,
and **Mark cancelled**. A cancelled event stays in the schedule struck through,
gets no reminders, and is skipped by `/next` and the closest-event answers.

## Reminding

Notifications are checked once a minute and are all optional:

- A reminder before the event, 15 minutes ahead by default, changed or turned
  off with `/remind`.
- A notice at the moment it starts, toggled with `/start_notice`.
- A daily digest of the day's events at a set time, `/digest HH:MM` or
  `/digest off`. Days without classes stay silent, and a digest missed by more
  than 30 minutes (the bot was down) is skipped rather than sent late.

Reminders and notices carry the room and the notes. `notified_at` is stored per
event, so a restart does not re-send what was already sent, and shortening the
reminder window does not fire a second time for an event already covered by the
old one. `/settings` shows everything in one place.

Reminders can be muted on the same three levels as notes: a whole subject or
one type of it from the subject's **Reminders** screen, a single class from its
card. The switches are listed from the types the timetable actually has, not
from a fixed list. The widest level wins, so a muted subject stays silent
whatever its types say. Muting only silences the reminder and the start notice;
the event still shows in the schedule and the digest. A failed delivery to one
user (a blocked bot, a Telegram error) is logged and skipped, so it never holds
up the notifications of everyone after them.

## Event types

The `.ics` summary carries the kind of class, mapped to `CV` (cvicenie), `P`
(prednaska) or `S` (seminar). MAIS exports assessments with the category
`Termin hodnotenia` and a `DURATION` instead of a `DTEND`; those become `EXAM`.
Anything unrecognised becomes `UNK` and is still imported - an unknown type is
worth less than a lost class.

The room shown in listings is the last parenthesised part of `LOCATION`
(`L9-A514`), the card shows the whole field.

## Testing against a different time

A bot whose whole job is time is hard to test at the moment you happen to be
running it, so the clock is a module rather than a direct `datetime.now()`
call, and it can be moved:

```
SEMESTRA_CLOCK_NOW=2026-10-06T08:45      # pin to an instant
SEMESTRA_CLOCK_OFFSET=+2d3h              # shift from the real clock
```

The offset is read once per process and logged loudly when set, so a shifted
clock cannot be mistaken for a real one.

## Environment

`.env` in the project root:

```
BOT_TOKEN=<token from @BotFather>
ADMIN_IDS=<your Telegram user id, comma separated for several>
```

`ADMIN_IDS` is never committed, so the repository can be public without naming
anyone. `/admin_info` prints usage totals and is the only admin surface; a user
who is not on the list gets no answer at all, so it cannot be found by guessing.

## Running

```
pip install -r requirements.txt
python -m bot.main
```

Python 3.14. The database is SQLite and is created on first run from
`db/schema.sql`.

## Deployment

Runs as a systemd user service (`deploy/semestra.service`), from
`~/projects/semestra`. A push to `main` triggers the workflow in
`.github/workflows/deploy.yml`, which pulls over SSH, installs requirements and
restarts the unit.

## Mini App demo

`demo/webapp` is a throwaway preview of how a Telegram Mini App for this bot
could look. Demo data only, no imports from the bot. See its own README.
