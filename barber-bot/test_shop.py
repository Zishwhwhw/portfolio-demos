from datetime import date, datetime, time, timedelta

import pytest

from shop import Store, Visit, any_barber_slots, barbers_for, book, free_slots, open_days

MON = date(2026, 11, 23)                     # a Monday
NOW = datetime(2026, 11, 22, 12, 0)          # Sunday noon, the shop is closed


def test_sunday_is_closed_and_skipped():
    assert free_slots(date(2026, 11, 22), "cut", "marek", [], NOW) == []
    days = open_days(NOW, 7)
    assert days[0] == MON and all(d.weekday() != 6 for d in days) and len(days) == 7


def test_slots_respect_hours_and_length():
    slots = free_slots(MON, "combo", "marek", [], NOW)    # 90 min, Mon 10–20
    assert slots[0] == time(10, 0) and slots[-1] == time(18, 30)
    sat = free_slots(date(2026, 11, 28), "cut", "marek", [], NOW)
    assert sat[0] == time(9, 0) and sat[-1] == time(15, 0)


def test_busy_barber_and_lead_time():
    taken = [Visit("cut", "marek", datetime(2026, 11, 23, 12, 0))]
    slots = free_slots(MON, "beard", "marek", taken, NOW)
    assert time(12, 0) not in slots and time(12, 30) not in slots and time(13, 0) in slots
    assert time(11, 30) in slots                          # 30-min beard ends exactly at 12:00
    morning = datetime(2026, 11, 23, 10, 10)
    assert free_slots(MON, "cut", "igor", [], morning)[0] == time(11, 30)   # at least 60 min ahead


def test_skills():
    assert barbers_for("kids") == ["marek"]
    assert free_slots(MON, "kids", "igor", [], NOW) == []
    with pytest.raises(ValueError, match="doesn't do"):
        book("shave", "igor", MON, time(10), [], NOW)


def test_any_barber_picks_who_is_free():
    taken = [Visit("cut", "marek", datetime(2026, 11, 23, 10, 0))]
    slots = any_barber_slots(MON, "cut", taken, NOW)
    assert slots[time(10, 0)] == "tomek"
    assert book("cut", "any", MON, time(10), taken, NOW).barber == "tomek"


def test_double_booking_is_rejected():
    st = Store()
    v = book("fade", "igor", MON, time(14), st.taken(), NOW)
    st.add(1, "Jan", v, NOW)
    with pytest.raises(ValueError, match="just taken"):
        book("cut", "igor", MON, time(14, 30), st.taken(), NOW)


def test_cancel_rules():
    st = Store()
    vid = st.add(7, "Jan", Visit("cut", "tomek", datetime(2026, 11, 23, 15)), NOW)
    assert st.cancel(vid, 8, NOW) == "missing"                                   # someone else's visit
    assert st.cancel(vid, 7, datetime(2026, 11, 23, 13)) == "late"               # 2 h before
    assert st.cancel(vid, 7, NOW) == "ok"
    assert st.upcoming(7, NOW) == []


def test_reminders_then_review_each_once():
    st = Store()
    start = datetime(2026, 11, 24, 15)
    vid = st.add(7, "Jan", Visit("cut", "tomek", start), NOW)
    assert st.due(start - timedelta(hours=30)) == []
    kinds = lambda t: [k for k, _ in st.due(t)]
    assert kinds(start - timedelta(hours=23)) == ["day"]
    st.mark(vid, "day")
    assert kinds(start - timedelta(hours=23)) == []
    assert kinds(start - timedelta(hours=1)) == ["soon"]
    st.mark(vid, "soon")
    assert kinds(start + timedelta(hours=2)) == []                               # visit ends 16:00, review at 18:00
    assert kinds(start + timedelta(hours=3)) == ["review"]
    st.mark(vid, "review")
    assert st.due(start + timedelta(hours=5)) == []
    assert st.rate(vid, 7, 5) and not st.rate(vid, 7, 1)                         # one rating per visit


def test_last_minute_booking_gets_no_reminders():
    st = Store()
    booked = datetime(2026, 11, 23, 13)
    st.add(7, "Jan", Visit("beard", "igor", datetime(2026, 11, 23, 14)), booked)
    assert st.due(datetime(2026, 11, 23, 13, 5)) == []                           # booked 1 h ahead: no "soon" ping
