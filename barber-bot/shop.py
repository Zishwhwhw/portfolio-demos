"""Business rules for Brzytwa barbershop: services, barbers, opening hours, free slots, bookings, reminders.

No Telegram code here, so the rules are unit-tested and can be reused by a web booking page later.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

SERVICES = {  # id: (name, minutes, price PLN)
    "cut": ("Haircut", 60, 90),
    "fade": ("Skin fade", 60, 100),
    "beard": ("Beard trim", 30, 60),
    "combo": ("Haircut + beard", 90, 140),
    "kids": ("Kids cut (under 12)", 45, 70),
    "shave": ("Head shave", 45, 70),
}
BARBERS = {  # id: (name, services)
    "marek": ("Marek", set(SERVICES)),
    "tomek": ("Tomek", set(SERVICES) - {"kids"}),
    "igor": ("Igor", {"cut", "fade", "beard", "combo"}),
}
HOURS = {0: (10, 20), 1: (10, 20), 2: (10, 20), 3: (10, 20), 4: (10, 20), 5: (9, 16)}  # weekday: (open, close); Sunday closed
STEP = 30           # minutes between possible start times
LEAD = 60           # earliest booking is one hour from now
CANCEL_BEFORE = timedelta(hours=3)
DAY_BEFORE, SOON_BEFORE = timedelta(hours=24), timedelta(hours=2)
REVIEW_AFTER = timedelta(hours=2)


@dataclass(frozen=True)
class Visit:
    service: str
    barber: str
    start: datetime

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=SERVICES[self.service][1])


def barbers_for(service: str) -> list[str]:
    return [b for b, (_, skills) in BARBERS.items() if service in skills]


def open_days(now: datetime, n: int = 7) -> list[date]:
    """The next n calendar days the shop is open, starting today."""
    out, d = [], now.date()
    while len(out) < n:
        if d.weekday() in HOURS:
            out.append(d)
        d += timedelta(days=1)
    return out


def free_slots(day: date, service: str, barber: str, taken: list[Visit], now: datetime) -> list[time]:
    """Start times where the barber is free for the whole service and the shop is open."""
    if service not in SERVICES or service not in BARBERS.get(barber, ("", set()))[1] or day.weekday() not in HOURS:
        return []
    o, c = HOURS[day.weekday()]
    length = timedelta(minutes=SERVICES[service][1])
    busy = [(v.start, v.end) for v in taken if v.barber == barber and v.start.date() == day]
    t, close, out = datetime.combine(day, time(o)), datetime.combine(day, time(c)), []
    while t + length <= close:
        if t >= now + timedelta(minutes=LEAD) and all(t + length <= s or t >= e for s, e in busy):
            out.append(t.time())
        t += timedelta(minutes=STEP)
    return out


def any_barber_slots(day: date, service: str, taken: list[Visit], now: datetime) -> dict[time, str]:
    """For "any barber": each free start time mapped to the first barber who has it."""
    out: dict[time, str] = {}
    for b in barbers_for(service):
        for t in free_slots(day, service, b, taken, now):
            out.setdefault(t, b)
    return dict(sorted(out.items()))


def book(service: str, barber: str, day: date, at: time, taken: list[Visit], now: datetime) -> Visit:
    """Re-check the slot at confirmation time (someone may have taken it meanwhile). Raises ValueError for the user."""
    if service not in SERVICES:
        raise ValueError("This service is not available.")
    if barber == "any":
        b = any_barber_slots(day, service, taken, now).get(at)
        if not b:
            raise ValueError("This time was just taken. Please pick another one.")
        barber = b
    elif service not in BARBERS.get(barber, ("", set()))[1]:
        raise ValueError(f"{BARBERS.get(barber, ('This barber',))[0]} doesn't do this service.")
    elif at not in free_slots(day, service, barber, taken, now):
        raise ValueError("This time was just taken. Please pick another one.")
    return Visit(service, barber, datetime.combine(day, at))


def describe(v: Visit) -> str:
    name, minutes, price = SERVICES[v.service]
    return f"{name} with {BARBERS[v.barber][0]}\n{v.start:%A %d %B, %H:%M} ({minutes} min) · {price} zł"


class Store:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY, user_id INT, name TEXT, service TEXT, barber TEXT, start TEXT,
            status TEXT DEFAULT 'booked', sent TEXT DEFAULT '', rating INT, created TEXT)""")

    def taken(self) -> list[Visit]:
        rows = self.db.execute("SELECT service, barber, start FROM visits WHERE status='booked'").fetchall()
        return [Visit(s, b, datetime.fromisoformat(t)) for s, b, t in rows]

    def add(self, user_id: int, name: str, v: Visit, now: datetime) -> int:
        cur = self.db.execute("INSERT INTO visits (user_id, name, service, barber, start, created) VALUES (?,?,?,?,?,?)",
                              (user_id, name, v.service, v.barber, v.start.isoformat(), now.isoformat()))
        self.db.commit()
        return cur.lastrowid

    def get(self, visit_id: int) -> tuple | None:
        return self.db.execute("SELECT id, user_id, name, service, barber, start, status FROM visits WHERE id=?",
                               (visit_id,)).fetchone()

    def upcoming(self, user_id: int, now: datetime) -> list[tuple]:
        rows = self.db.execute("SELECT id, service, barber, start FROM visits WHERE user_id=? AND status='booked' "
                               "ORDER BY start", (user_id,)).fetchall()
        return [r for r in rows if datetime.fromisoformat(r[3]) > now]

    def cancel(self, visit_id: int, user_id: int, now: datetime) -> str:
        """→ 'ok', 'late' (less than 3 h before) or 'missing'."""
        row = self.get(visit_id)
        if not row or row[1] != user_id or row[6] != "booked":
            return "missing"
        if datetime.fromisoformat(row[5]) - now < CANCEL_BEFORE:
            return "late"
        self.db.execute("UPDATE visits SET status='cancelled' WHERE id=?", (visit_id,))
        self.db.commit()
        return "ok"

    def due(self, now: datetime) -> list[tuple[str, tuple]]:
        """Messages to send now: ('day'|'soon', visit) reminders and ('review', visit) after the visit. Each goes once."""
        out = []
        for row in self.db.execute("SELECT id, user_id, service, barber, start, sent, created FROM visits "
                                   "WHERE status='booked'").fetchall():
            start, sent, created = datetime.fromisoformat(row[4]), row[5].split(","), datetime.fromisoformat(row[6])
            left, end = start - now, start + timedelta(minutes=SERVICES[row[2]][1])
            # a reminder only makes sense if the visit was booked before that reminder's window opened
            if timedelta(0) < left <= SOON_BEFORE and "soon" not in sent and start - created > SOON_BEFORE:
                out.append(("soon", row[:5]))
            elif SOON_BEFORE < left <= DAY_BEFORE and "day" not in sent and start - created > DAY_BEFORE:
                out.append(("day", row[:5]))
            elif now >= end + REVIEW_AFTER and "review" not in sent:
                out.append(("review", row[:5]))
        return out

    def mark(self, visit_id: int, kind: str) -> None:
        sent = self.db.execute("SELECT sent FROM visits WHERE id=?", (visit_id,)).fetchone()[0]
        self.db.execute("UPDATE visits SET sent=? WHERE id=?", (",".join(filter(None, [sent, kind])), visit_id))
        self.db.commit()

    def rate(self, visit_id: int, user_id: int, stars: int) -> bool:
        cur = self.db.execute("UPDATE visits SET rating=? WHERE id=? AND user_id=? AND rating IS NULL",
                              (max(1, min(5, stars)), visit_id, user_id))
        self.db.commit()
        return cur.rowcount == 1

    def day_list(self, day: date) -> list[tuple]:
        rows = self.db.execute("SELECT start, service, barber, name FROM visits WHERE status='booked' ORDER BY start").fetchall()
        return [r for r in rows if datetime.fromisoformat(r[0]).date() == day]
