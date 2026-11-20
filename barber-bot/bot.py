"""Brzytwa barbershop booking bot (aiogram 3).

Clients book with inline buttons: service → barber → day → time → confirm.
The shop chat gets every booking and cancellation; clients get reminders 24 h and 2 h before
and a rating request after the visit.

    BOT_TOKEN=... ADMIN_CHAT_ID=... python bot.py
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop import (BARBERS, SERVICES, Store, Visit, any_barber_slots, barbers_for, book, describe, free_slots,
                  open_days)

TZ = ZoneInfo("Europe/Warsaw")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
REVIEW_URL = os.getenv("REVIEW_URL", "https://g.page/r/your-place-id/review")
ADDRESS = ("ul. Ruska 18, Wrocław", 51.1103, 17.0268)
PHOTO = Path(__file__).parent / "img" / "chair.jpg"

store = Store(os.getenv("DB_PATH", "barber.db"))
router = Router()
log = logging.getLogger("barber")


def now() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


class Menu(CallbackData, prefix="m"):
    action: str                                  # book | visits | prices | where | home


class Pick(CallbackData, prefix="p"):
    step: str                                    # svc | bar | day | full | time | ok
    svc: str = ""
    bar: str = ""
    day: str = ""                                # YYYYMMDD
    at: str = ""                                 # HHMM


class Act(CallbackData, prefix="a"):
    action: str                                  # cancel | rate | fine
    vid: int
    n: int = 0


def home_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✂️ Book a visit", callback_data=Menu(action="book"))
    kb.button(text="📅 My visits", callback_data=Menu(action="visits"))
    kb.button(text="💈 Prices", callback_data=Menu(action="prices"))
    kb.button(text="📍 How to find us", callback_data=Menu(action="where"))
    kb.adjust(1, 2, 1)
    return kb.as_markup()


def back(kb: InlineKeyboardBuilder, cb: CallbackData, text: str = "‹ Back") -> None:
    kb.row()
    kb.button(text=text, callback_data=cb)


@router.message(CommandStart())
async def start(m: Message):
    text = (f"Hi, {m.from_user.first_name}! This is Brzytwa barbershop on Ruska street.\n\n"
            "Book a cut in four taps. We remind you the day before and two hours before.")
    if PHOTO.exists():
        await m.answer_photo(FSInputFile(PHOTO), caption=text, reply_markup=home_kb())
    else:
        await m.answer(text, reply_markup=home_kb())


@router.callback_query(Menu.filter(F.action == "home"))
async def home(c: CallbackQuery):
    await c.message.answer("What would you like to do?", reply_markup=home_kb())
    await c.answer()


@router.callback_query(Menu.filter(F.action == "prices"))
async def prices(c: CallbackQuery):
    lines = [f"{name} — {price} zł · {minutes} min" for name, minutes, price in SERVICES.values()]
    await c.message.answer("💈 Prices\n\n" + "\n".join(lines) + "\n\nCard or cash, paid after the visit.")
    await c.answer()


@router.callback_query(Menu.filter(F.action == "where"))
async def where(c: CallbackQuery):
    await c.message.answer_location(ADDRESS[1], ADDRESS[2])
    await c.message.answer(f"📍 {ADDRESS[0]}\nMon–Fri 10:00–20:00, Sat 9:00–16:00, Sunday closed.")
    await c.answer()


# ---------- booking flow ----------
@router.callback_query(Menu.filter(F.action == "book"))
async def choose_service(c: CallbackQuery):
    kb = InlineKeyboardBuilder()
    for sid, (name, minutes, price) in SERVICES.items():
        kb.button(text=f"{name} · {price} zł", callback_data=Pick(step="svc", svc=sid))
    kb.adjust(1)
    await c.message.answer("Which service?", reply_markup=kb.as_markup())
    await c.answer()


@router.callback_query(Pick.filter(F.step == "svc"))
async def choose_barber(c: CallbackQuery, callback_data: Pick):
    kb = InlineKeyboardBuilder()
    for b in barbers_for(callback_data.svc):
        kb.button(text=BARBERS[b][0], callback_data=Pick(step="bar", svc=callback_data.svc, bar=b))
    kb.button(text="Any barber", callback_data=Pick(step="bar", svc=callback_data.svc, bar="any"))
    kb.adjust(3, 1)
    back(kb, Menu(action="book"))
    await c.message.edit_text(f"{SERVICES[callback_data.svc][0]}. Who should do it?", reply_markup=kb.as_markup())
    await c.answer()


def slots_for(svc: str, bar: str, day: date) -> dict[time, str]:
    taken, t = store.taken(), now()
    if bar == "any":
        return any_barber_slots(day, svc, taken, t)
    return {s: bar for s in free_slots(day, svc, bar, taken, t)}


@router.callback_query(Pick.filter(F.step == "bar"))
async def choose_day(c: CallbackQuery, callback_data: Pick):
    kb = InlineKeyboardBuilder()
    for d in open_days(now()):
        free = len(slots_for(callback_data.svc, callback_data.bar, d))
        label = f"{d:%a %d}" + ("" if free else " · full")
        step = "day" if free else "full"
        kb.button(text=label, callback_data=Pick(step=step, svc=callback_data.svc, bar=callback_data.bar,
                                                 day=f"{d:%Y%m%d}"))
    kb.adjust(4)
    back(kb, Pick(step="svc", svc=callback_data.svc))
    await c.message.edit_text("Which day?", reply_markup=kb.as_markup())
    await c.answer()


@router.callback_query(Pick.filter(F.step == "full"))
async def full_day(c: CallbackQuery):
    await c.answer("No free time that day. Try another one.", show_alert=True)


@router.callback_query(Pick.filter(F.step == "day"))
async def choose_time(c: CallbackQuery, callback_data: Pick):
    d = datetime.strptime(callback_data.day, "%Y%m%d").date()
    slots = slots_for(callback_data.svc, callback_data.bar, d)
    kb = InlineKeyboardBuilder()
    for t in slots:
        kb.button(text=f"{t:%H:%M}", callback_data=Pick(step="time", svc=callback_data.svc, bar=callback_data.bar,
                                                        day=callback_data.day, at=f"{t:%H%M}"))
    kb.adjust(4)
    back(kb, Pick(step="bar", svc=callback_data.svc, bar=callback_data.bar))
    text = f"{d:%A %d %B}. Free times:" if slots else "Someone just took the last slot that day. Pick another day."
    await c.message.edit_text(text, reply_markup=kb.as_markup())
    await c.answer()


@router.callback_query(Pick.filter(F.step == "time"))
async def confirm(c: CallbackQuery, callback_data: Pick):
    d = datetime.strptime(callback_data.day + callback_data.at, "%Y%m%d%H%M")
    bar = callback_data.bar if callback_data.bar != "any" else slots_for(callback_data.svc, "any", d.date()).get(d.time())
    if not bar:
        await c.answer("That time was just taken.", show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Confirm", callback_data=Pick(step="ok", svc=callback_data.svc, bar=callback_data.bar,
                                                   day=callback_data.day, at=callback_data.at))
    kb.button(text="Change time", callback_data=Pick(step="day", svc=callback_data.svc, bar=callback_data.bar,
                                                     day=callback_data.day))
    kb.adjust(1)
    await c.message.edit_text("Check the details:\n\n" + describe(Visit(callback_data.svc, bar, d)),
                              reply_markup=kb.as_markup())
    await c.answer()


@router.callback_query(Pick.filter(F.step == "ok"))
async def booked(c: CallbackQuery, callback_data: Pick, bot: Bot):
    d = datetime.strptime(callback_data.day + callback_data.at, "%Y%m%d%H%M")
    try:
        v = book(callback_data.svc, callback_data.bar, d.date(), d.time(), store.taken(), now())
    except ValueError as e:
        await c.answer(str(e), show_alert=True)
        return
    vid = store.add(c.from_user.id, c.from_user.full_name, v, now())
    await c.message.edit_text(f"Booked ✂️\n\n{describe(v)}\n📍 {ADDRESS[0]}\n\n"
                              "We’ll remind you the day before. You can cancel up to 3 hours before in “My visits”.")
    await c.answer("Booked!")
    if ADMIN_CHAT_ID:
        user = f"@{c.from_user.username}" if c.from_user.username else c.from_user.full_name
        await bot.send_message(ADMIN_CHAT_ID, f"🆕 Booking #{vid}\n{describe(v)}\nClient: {user}")


# ---------- my visits ----------
@router.callback_query(Menu.filter(F.action == "visits"))
async def visits(c: CallbackQuery):
    rows = store.upcoming(c.from_user.id, now())
    if not rows:
        kb = InlineKeyboardBuilder()
        kb.button(text="✂️ Book a visit", callback_data=Menu(action="book"))
        await c.message.answer("No upcoming visits.", reply_markup=kb.as_markup())
        return await c.answer()
    for vid, svc, bar, start in rows:
        kb = InlineKeyboardBuilder()
        kb.button(text="Cancel this visit", callback_data=Act(action="cancel", vid=vid))
        await c.message.answer(describe(Visit(svc, bar, datetime.fromisoformat(start))), reply_markup=kb.as_markup())
    await c.answer()


@router.callback_query(Act.filter(F.action == "cancel"))
async def cancel(c: CallbackQuery, callback_data: Act, bot: Bot):
    row = store.get(callback_data.vid)
    result = store.cancel(callback_data.vid, c.from_user.id, now())
    if result == "late":
        return await c.answer("Less than 3 hours left. Please call us: +48 71 000 00 00", show_alert=True)
    if result == "missing":
        return await c.answer("This visit is already cancelled.", show_alert=True)
    await c.message.edit_text("Cancelled. The time is free again for someone else.")
    await c.answer()
    if ADMIN_CHAT_ID:
        await bot.send_message(ADMIN_CHAT_ID, f"❌ Cancelled #{row[0]}: "
                                              f"{describe(Visit(row[3], row[4], datetime.fromisoformat(row[5])))}")


# ---------- reminders and reviews ----------
@router.callback_query(Act.filter(F.action == "fine"))
async def fine(c: CallbackQuery):
    await c.message.edit_reply_markup(reply_markup=None)
    await c.answer("See you!")


@router.callback_query(Act.filter(F.action == "rate"))
async def rate(c: CallbackQuery, callback_data: Act, bot: Bot):
    if not store.rate(callback_data.vid, c.from_user.id, callback_data.n):
        return await c.answer("Already rated, thank you!")
    await c.message.edit_reply_markup(reply_markup=None)
    if callback_data.n == 5:
        kb = InlineKeyboardBuilder()
        kb.button(text="Leave a Google review", url=REVIEW_URL)
        await c.message.answer("Thank you! If you have a minute, a Google review helps us a lot.",
                               reply_markup=kb.as_markup())
    else:
        await c.message.answer("Thanks for being honest. Reply here with what we could do better, the owner reads it.")
        if ADMIN_CHAT_ID:
            await bot.send_message(ADMIN_CHAT_ID, f"⭐ {callback_data.n}/5 for visit #{callback_data.vid}")
    await c.answer()


async def reminder_loop(bot: Bot):
    while True:
        for kind, (vid, user_id, svc, bar, start) in store.due(now()):
            v = Visit(svc, bar, datetime.fromisoformat(start))
            kb = InlineKeyboardBuilder()
            if kind == "review":
                for n in range(1, 6):
                    kb.button(text="⭐" * n if n in (1, 5) else str(n), callback_data=Act(action="rate", vid=vid, n=n))
                kb.adjust(5)
                text = f"How was your {SERVICES[svc][0].lower()} with {BARBERS[bar][0]}?"
            else:
                kb.button(text="👍 See you", callback_data=Act(action="fine", vid=vid))
                kb.button(text="Cancel", callback_data=Act(action="cancel", vid=vid))
                when = "Tomorrow" if kind == "day" else "In 2 hours"
                text = f"⏰ {when}: {describe(v)}\n📍 {ADDRESS[0]}"
            try:
                await bot.send_message(user_id, text, reply_markup=kb.as_markup())
            except Exception as e:                       # user blocked the bot: don't retry every minute
                log.warning("reminder %s to %s failed: %s", vid, user_id, e)
            store.mark(vid, kind)
        await asyncio.sleep(60)


@router.message(Command("today"), F.chat.id == ADMIN_CHAT_ID)
async def today(m: Message):
    rows = store.day_list(now().date())
    if not rows:
        return await m.answer("No bookings today.")
    await m.answer("Today:\n" + "\n".join(f"{datetime.fromisoformat(s):%H:%M} {SERVICES[svc][0]} · "
                                          f"{BARBERS[b][0]} · {name}" for s, svc, b, name in rows))


async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(os.environ["BOT_TOKEN"])
    dp = Dispatcher()
    dp.include_router(router)
    asyncio.create_task(reminder_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
