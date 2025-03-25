import os
import json
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, BotCommand
from aiogram.filters import Command

# ================= НАСТРОЙКА =================
TOKEN = os.getenv("TOKEN")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS = json.loads(os.getenv("GOOGLE_CREDS"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
PORT = int(os.getenv("PORT", 8080))

# ================= GOOGLE SHEETS =================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDS, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# ================= ЛОГИ =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= БОТ =================
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ================= КОМАНДЫ =================
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="total", description="Посмотреть расходы за день"),
        BotCommand(command="debug", description="Отладка"),
    ]
    await bot.set_my_commands(commands)

# ================= ХЕНДЛЕРЫ =================
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Привет! Отправь сумму и категорию расхода. Например: 500 Еда")

@router.message(Command("total"))
async def cmd_total(message: Message):
    today = datetime.now().strftime("%Y-%m-%d")
    records = sheet.get_all_values()
    header = records[0]
    if "Дата" not in header or "Сумма" not in header:
        await message.answer("Ошибка: нет колонок 'Дата' или 'Сумма'")
        return
    date_col = header.index("Дата") + 1
    amount_col = header.index("Сумма") + 1
    total = sum(int(row[amount_col - 1]) for row in records[1:] if row[date_col - 1] == today)
    await message.answer(f"💰 Итог за {today}: {total} руб.")

@router.message(Command("debug"))
async def cmd_debug(message: Message):
    records = sheet.get_all_values()
    await message.answer(f"🔍 Данные в таблице:\n{records if records else 'пусто'}")

@router.message()
async def add_expense(message: Message):
    try:
        amount, category = message.text.split(" ", 1)
        amount = int(amount)
        date = datetime.now().strftime("%Y-%m-%d")
        sheet.append_row([date, amount, category])
        await message.answer(f"✅ Записано: {amount} руб. на {category} ({date})")
    except ValueError:
        await message.answer("Ошибка! Отправь в формате: 500 Еда")
    except Exception as e:
        logger.exception("Ошибка при записи")
        await message.answer("Ошибка при записи")

# ================= ВЕБХУК =================
async def telegram_webhook(request: web.Request):
    try:
        data = await request.json()
        logger.info(f"📥 Входящий апдейт: {data}")

        if data.get("ping") == "true":
            return web.json_response({"status": "ok", "message": "pong"})

        await dp.feed_raw_update(bot=bot, update=data)
        return web.Response(text="ok")
    except Exception as e:
        logger.exception("❌ Ошибка в webhook")
        return web.Response(status=500, text="webhook error")

# ================= СЕРВЕР =================
app = web.Application()
app.router.add_post(f"/webhook/{WEBHOOK_SECRET}", telegram_webhook)
app.router.add_get("/", lambda r: web.Response(text="pong"))

app.on_startup.append(lambda app: set_commands(bot))
app.on_shutdown.append(lambda app: bot.session.close())

# ================= ЗАПУСК =================
if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
