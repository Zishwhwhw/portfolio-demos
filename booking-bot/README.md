# Lumi salon booking bot (portfolio demo)

Telegram bot + Mini App for booking beauty salon visits. Lumi is a fictional salon.

- **Mini App** (`../booking/`): choose a service, a master (or "any"), a day and a free time. Uses Telegram theme colours, MainButton and haptics; works in a normal browser too.
- **Bot** (`main.py`, aiogram 3): opens the Mini App, re-checks the chosen time on the server, stores the visit in SQLite, notifies the salon admin, lets clients see and cancel visits, and sends a reminder 2 hours before.
- **Rules** (`salon.py`): opening hours, 15-minute grid, service length, master skills, no overlaps, no bookings in the next 30 minutes. Shared by bot and tests.

```bash
pip install -r requirements.txt
pytest -q                      # 7 tests
BOT_TOKEN=... ADMIN_ID=... WEBAPP_URL=https://zishwhwhw.github.io/portfolio-demos/booking/ python main.py
```

Live Mini App: https://zishwhwhw.github.io/portfolio-demos/booking/
