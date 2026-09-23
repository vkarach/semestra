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
- `/today`, `/week` - the current day or week
- `/schedule` - the next 7 days, starting from the next event rather than from
  today, so a request made on a free Saturday still shows a full week

An empty answer names the closest event instead of saying nothing.

## Reminding

Two notifications, both optional and both checked once a minute:

- A reminder before the event, 15 minutes ahead by default, changed with
  `/remind`.
- A notice at the moment it starts, toggled with `/start_notice`.

`notified_at` is stored per event, so a restart does not re-send what was
already sent, and shortening the reminder window does not fire a second time
for an event already covered by the old one.

## Event types

The `.ics` summary carries the kind of class, mapped to `CV` (cvicenie), `P`
(prednaska) or `S` (seminar). Anything unrecognised becomes `UNK` and is still
imported - an unknown type is worth less than a lost class.

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
