"""Lumi salon bot (aiogram 3): opens the booking Mini App, validates and stores visits,
notifies the salon admin, lets clients cancel and sends a reminder 2 hours before the visit.

Run:  BOT_TOKEN=... ADMIN_ID=... WEBAPP_URL=https://<you>.github.io/portfolio-demos/booking/ python main.py
"""
import asyncio
import json
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message,
                           ReplyKeyboardMarkup, WebAppInfo)

from salon import Store, describe, validate

store = Store(os.getenv("DB_PATH", "bookings.db"))
dp = Dispatcher()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="💅 Book a visit", web_app=WebAppInfo(url=os.environ["WEBAPP_URL"]))],
        [KeyboardButton(text="📅 My visits")]])


@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("Hi! I’m the Lumi salon assistant. Tap “Book a visit” to choose a service, master and time.",
                   reply_markup=main_kb())


@dp.message(F.web_app_data)
async def booked(m: Message, bot: Bot):
    try:
        b = validate(json.loads(m.web_app_data.data), store.active(), datetime.now())
    except (ValueError, json.JSONDecodeError) as e:
        await m.answer(f"⚠️ {e}", reply_markup=main_kb())
        return
    bid = store.add(m.from_user.id, m.from_user.full_name, b)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Cancel visit", callback_data=f"cancel:{bid}")]])
    await m.answer(f"✅ Booked: {describe(b.service, b.master, b.start)}.\nI’ll remind you 2 hours before.",
                   reply_markup=kb)
    if ADMIN_ID:
        await bot.send_message(ADMIN_ID, f"🆕 Visit #{bid}\n{describe(b.service, b.master, b.start)}\n"
                                         f"Client: {m.from_user.full_name} (@{m.from_user.username or '—'})")


@dp.message(F.text == "📅 My visits")
async def my_visits(m: Message):
    rows = store.for_user(m.from_user.id)
    if not rows:
        await m.answer("You have no upcoming visits. Tap “Book a visit” to make one.")
        return
    for bid, service, master, start in rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Cancel visit", callback_data=f"cancel:{bid}")]])
        await m.answer(describe(service, master, datetime.fromisoformat(start)), reply_markup=kb)


@dp.callback_query(F.data.startswith("cancel:"))
async def cancel(c: CallbackQuery, bot: Bot):
    bid = int(c.data.split(":")[1])
    if store.cancel(bid, c.from_user.id):
        await c.message.edit_text(c.message.text + "\n\n❌ Cancelled. The time is free for others again.")
        if ADMIN_ID:
            await bot.send_message(ADMIN_ID, f"❌ Visit #{bid} cancelled by the client.")
    await c.answer()


async def reminders(bot: Bot):
    while True:
        for bid, user_id, service, master, start in store.due_reminders(datetime.now()):
            await bot.send_message(user_id, f"⏰ Reminder: {describe(service, master, datetime.fromisoformat(start))}.")
            store.mark_reminded(bid)
        await asyncio.sleep(60)


async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(os.environ["BOT_TOKEN"])
    asyncio.create_task(reminders(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
