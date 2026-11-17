"""Pixel Plants bot — aiogram 3 demo: menu, Mini App orders, Telegram Stars payments, SQLite, admin alerts.

Run:  BOT_TOKEN=... ADMIN_ID=... WEBAPP_URL=https://<you>.github.io/portfolio-demos/miniapp/ python main.py
"""
import asyncio, json, logging, os, sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (KeyboardButton, LabeledPrice, Message, PreCheckoutQuery, ReplyKeyboardMarkup, WebAppInfo)

CATALOG = {1: ("Monstera", 120), 2: ("Cactus trio", 45), 3: ("Snake plant", 90),
           4: ("Sunflower", 30), 5: ("Tulip box", 55), 6: ("Bonsai", 150)}
DB = sqlite3.connect(os.getenv("DB_PATH", "orders.db"))
DB.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user_id INT, items TEXT, total INT, status TEXT)")

dp = Dispatcher()


def order_total(items: list[dict]) -> tuple[int, str]:
    """Validate an order coming from the Mini App against the server-side catalog."""
    total, lines = 0, []
    for it in items:
        name, price = CATALOG[int(it["id"])]
        qty = max(1, min(int(it["qty"]), 20))
        total += price * qty
        lines.append(f"{name} × {qty}")
    if not lines:
        raise ValueError("empty order")
    return total, ", ".join(lines)


@dp.message(CommandStart())
async def start(m: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="🪴 Open shop", web_app=WebAppInfo(url=os.environ["WEBAPP_URL"]))],
                                                             [KeyboardButton(text="📦 My orders")]])
    await m.answer("Welcome to Pixel Plants! Tap the button to open the shop.", reply_markup=kb)


@dp.message(F.text == "📦 My orders")
async def my_orders(m: Message):
    rows = DB.execute("SELECT id, items, total, status FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5", (m.from_user.id,)).fetchall()
    await m.answer("\n".join(f"#{r[0]} · {r[1]} · ⭐{r[2]} · {r[3]}" for r in rows) or "No orders yet.")


@dp.message(F.web_app_data)
async def from_mini_app(m: Message, bot: Bot):
    total, text = order_total(json.loads(m.web_app_data.data))
    oid = DB.execute("INSERT INTO orders (user_id, items, total, status) VALUES (?,?,?, 'awaiting payment')",
                     (m.from_user.id, text, total)).lastrowid
    DB.commit()
    await bot.send_invoice(m.chat.id, title=f"Order #{oid}", description=text, payload=str(oid),
                           currency="XTR", prices=[LabeledPrice(label="Plants", amount=total)])


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@dp.message(F.successful_payment)
async def paid(m: Message, bot: Bot):
    oid = int(m.successful_payment.invoice_payload)
    DB.execute("UPDATE orders SET status='paid' WHERE id=?", (oid,)); DB.commit()
    await m.answer(f"✅ Order #{oid} paid. We'll ship it today!")
    if os.getenv("ADMIN_ID"):
        await bot.send_message(int(os.environ["ADMIN_ID"]), f"🔔 New paid order #{oid} from @{m.from_user.username}")


@dp.message(Command("stats"))
async def stats(m: Message):
    if str(m.from_user.id) != os.getenv("ADMIN_ID"):
        return
    n, s = DB.execute("SELECT COUNT(*), COALESCE(SUM(total),0) FROM orders WHERE status='paid'").fetchone()
    await m.answer(f"Paid orders: {n}, revenue: ⭐{s}")


async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(Bot(os.environ["BOT_TOKEN"]))


if __name__ == "__main__":
    asyncio.run(main())
