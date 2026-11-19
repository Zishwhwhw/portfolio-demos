"""Business rules for Lumi salon bookings: catalog, opening hours, free slots, validation, storage.

Kept free of Telegram code so it can be unit-tested and reused by a web backend.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

SERVICES = {  # id: (name, minutes, price PLN)
    "mani": ("Classic manicure", 45, 90),
    "gel": ("Gel manicure", 75, 140),
    "pedi": ("Pedicure", 60, 130),
    "brows": ("Brow shaping + tint", 40, 80),
    "lam": ("Brow lamination", 60, 150),
    "lash": ("Lash lift", 60, 160),
}
MASTERS = {  # id: (name, services)
    "ola": ("Ola", {"mani", "gel", "pedi"}),
    "kasia": ("Kasia", {"mani", "gel", "brows", "lam"}),
    "iza": ("Iza", {"brows", "lam", "lash"}),
}
OPEN, CLOSE, STEP = time(9, 0), time(20, 0), 15  # minutes grid
CLOSED_WEEKDAYS = {6}  # Sunday


@dataclass(frozen=True)
class Booking:
    service: str
    master: str
    start: datetime

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=SERVICES[self.service][1])


def masters_for(service: str) -> list[str]:
    return [m for m, (_, skills) in MASTERS.items() if service in skills]


def free_slots(day: date, service: str, master: str, taken: list[Booking], now: datetime) -> list[time]:
    """Start times where the master is free for the whole service and the salon is open."""
    if service not in SERVICES or service not in MASTERS.get(master, ("", set()))[1]:
        return []
    if day.weekday() in CLOSED_WEEKDAYS:
        return []
    length = timedelta(minutes=SERVICES[service][1])
    busy = [(b.start, b.end) for b in taken if b.master == master and b.start.date() == day]
    t = datetime.combine(day, OPEN)
    close = datetime.combine(day, CLOSE)
    out = []
    while t + length <= close:
        if t > now + timedelta(minutes=30) and all(t + length <= s or t >= e for s, e in busy):
            out.append(t.time())
        t += timedelta(minutes=STEP)
    return out


def validate(data: dict, taken: list[Booking], now: datetime) -> Booking:
    """Check a request from the Mini App against server-side rules. Raises ValueError with a user-facing reason."""
    service, master = data.get("service"), data.get("master")
    if service not in SERVICES:
        raise ValueError("This service is not available.")
    if master == "any":
        try:
            day = date.fromisoformat(data["date"])
            at = time.fromisoformat(data["time"])
        except (KeyError, ValueError):
            raise ValueError("Pick a day and time.")
        for m in masters_for(service):
            if at in free_slots(day, service, m, taken, now):
                return Booking(service, m, datetime.combine(day, at))
        raise ValueError("This time was just taken. Please pick another one.")
    if master not in MASTERS or service not in MASTERS[master][1]:
        raise ValueError("This master doesn't do that service.")
    try:
        day = date.fromisoformat(data["date"])
        at = time.fromisoformat(data["time"])
    except (KeyError, ValueError):
        raise ValueError("Pick a day and time.")
    if at not in free_slots(day, service, master, taken, now):
        raise ValueError("This time was just taken. Please pick another one.")
    return Booking(service, master, datetime.combine(day, at))


class Store:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY, user_id INT, name TEXT, service TEXT, master TEXT, start TEXT,
            status TEXT DEFAULT 'booked', reminded INT DEFAULT 0)""")

    def active(self) -> list[Booking]:
        rows = self.db.execute("SELECT service, master, start FROM bookings WHERE status='booked'").fetchall()
        return [Booking(s, m, datetime.fromisoformat(t)) for s, m, t in rows]

    def add(self, user_id: int, name: str, b: Booking) -> int:
        cur = self.db.execute("INSERT INTO bookings (user_id, name, service, master, start) VALUES (?,?,?,?,?)",
                              (user_id, name, b.service, b.master, b.start.isoformat()))
        self.db.commit()
        return cur.lastrowid

    def for_user(self, user_id: int) -> list[tuple]:
        return self.db.execute("SELECT id, service, master, start FROM bookings WHERE user_id=? AND status='booked' "
                               "ORDER BY start", (user_id,)).fetchall()

    def cancel(self, booking_id: int, user_id: int) -> bool:
        cur = self.db.execute("UPDATE bookings SET status='cancelled' WHERE id=? AND user_id=? AND status='booked'",
                              (booking_id, user_id))
        self.db.commit()
        return cur.rowcount == 1

    def due_reminders(self, now: datetime, ahead: timedelta = timedelta(hours=2)) -> list[tuple]:
        rows = self.db.execute("SELECT id, user_id, service, master, start FROM bookings "
                               "WHERE status='booked' AND reminded=0").fetchall()
        return [r for r in rows if now <= datetime.fromisoformat(r[4]) <= now + ahead]

    def mark_reminded(self, booking_id: int) -> None:
        self.db.execute("UPDATE bookings SET reminded=1 WHERE id=?", (booking_id,))
        self.db.commit()


def describe(service: str, master: str, start: datetime) -> str:
    name, minutes, price = SERVICES[service]
    return f"{name} with {MASTERS[master][0]}, {start:%a %d %b at %H:%M} ({minutes} min, {price} zł)"
