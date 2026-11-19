from datetime import date, datetime, time, timedelta

import pytest

from salon import Booking, Store, free_slots, masters_for, validate

NOW = datetime(2026, 11, 24, 8, 0)   # Monday morning
DAY = date(2026, 11, 25)              # Wednesday


def test_slots_respect_opening_hours_and_length():
    slots = free_slots(DAY, "gel", "ola", [], NOW)        # 75 min
    assert slots[0] == time(9, 0)
    assert slots[-1] == time(18, 45)                      # 18:45 + 75 min = 20:00 closing


def test_sunday_closed_and_wrong_master():
    assert free_slots(date(2026, 11, 29), "mani", "ola", [], NOW) == []
    assert free_slots(DAY, "lash", "ola", [], NOW) == []   # Ola doesn't do lashes


def test_existing_booking_blocks_overlap_only():
    taken = [Booking("gel", "ola", datetime(2026, 11, 25, 12, 0))]   # 12:00-13:15
    slots = free_slots(DAY, "mani", "ola", taken, NOW)               # 45 min
    assert time(11, 15) in slots          # ends exactly at 12:00
    assert time(11, 30) not in slots      # would overlap
    assert time(13, 0) not in slots
    assert time(13, 15) in slots
    assert time(12, 0) in free_slots(DAY, "mani", "kasia", taken, NOW)   # other master is free


def test_no_slots_in_the_next_30_minutes():
    now = datetime(2026, 11, 25, 10, 0)
    assert min(free_slots(DAY, "mani", "ola", [], now)) == time(10, 45)


def test_validate_rejects_taken_time_and_any_master_picks_free_one():
    taken = [Booking("brows", "kasia", datetime(2026, 11, 25, 10, 0))]
    with pytest.raises(ValueError, match="just taken"):
        validate({"service": "brows", "master": "kasia", "date": "2026-11-25", "time": "10:00"}, taken, NOW)
    b = validate({"service": "brows", "master": "any", "date": "2026-11-25", "time": "10:00"}, taken, NOW)
    assert b.master == "iza" and b.master in masters_for("brows")


def test_validate_rejects_unknown_service():
    with pytest.raises(ValueError):
        validate({"service": "tattoo", "master": "ola", "date": "2026-11-25", "time": "10:00"}, [], NOW)


def test_store_add_cancel_and_reminders():
    s = Store()
    b = Booking("mani", "ola", datetime(2026, 11, 25, 11, 0))
    bid = s.add(1, "Anna", b)
    assert s.active() == [b]
    assert [r[0] for r in s.due_reminders(datetime(2026, 11, 25, 9, 30))] == [bid]
    s.mark_reminded(bid)
    assert s.due_reminders(datetime(2026, 11, 25, 9, 30)) == []
    assert not s.cancel(bid, user_id=2)          # someone else can't cancel
    assert s.cancel(bid, user_id=1)
    assert s.active() == []
