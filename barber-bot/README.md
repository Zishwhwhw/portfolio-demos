# Brzytwa: barbershop booking bot (aiogram 3)

**Try it in the browser:** https://zishwhwhw.github.io/portfolio-demos/barber-bot/
(the page runs the same booking rules as `shop.py`, plus a staff chat and time-travel buttons to see reminders).

Brzytwa is a fictional barbershop. This is a portfolio demo.

## What the bot does

- **Booking with inline buttons:** service → barber (or “any barber”) → day → free time → confirm.
- **No double bookings:** the slot is checked again at confirmation, in case someone took it meanwhile.
- **Opening hours:** Mon–Fri 10–20, Sat 9–16, Sunday closed. Each service has its own length, and the earliest booking is one hour ahead.
- **Staff group chat:** gets every booking and cancellation; `/today` lists the day’s visits.
- **Reminders:** 24 h and 2 h before the visit. A visit booked later than a reminder’s window doesn’t get that reminder.
- **Cancelling:** possible in “My visits” up to 3 h before.
- **After the visit:** the client is asked for a 1–5 rating. Five stars lead to a Google review link, and lower ratings go to the owner.

## Files

| File | |
|---|---|
| `shop.py` | Business rules with no Telegram code: services, barbers, hours, free slots, booking, SQLite storage, reminder schedule |
| `bot.py` | aiogram 3 handlers, typed `CallbackData`, reminder loop |
| `test_shop.py` | pytest: hours, service length, busy barbers, “any barber”, double booking, cancel rules, reminders |
| `index.html` | In-browser simulator for the portfolio |

## Run

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest -q                                   # 9 passed
BOT_TOKEN=123:abc ADMIN_CHAT_ID=-100123 python bot.py
```

Optional environment variables:

- `DB_PATH`: SQLite file, default `barber.db`.
- `REVIEW_URL`: Google review link.

Photos: see [credits](../credits.html).
