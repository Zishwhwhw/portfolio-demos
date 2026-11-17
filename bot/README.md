# Pixel Plants bot (aiogram 3)

Demo Telegram bot paired with the [Mini App](../miniapp/): reply-keyboard menu, orders sent from the Mini App via `web_app_data`,
server-side price validation, Telegram Stars invoices (`XTR`), SQLite order history, admin notifications and `/stats`.

```bash
pip install -r requirements.txt
BOT_TOKEN=... ADMIN_ID=... WEBAPP_URL=https://<you>.github.io/portfolio-demos/miniapp/ python main.py
pytest -q
```
