import os
import json
import logging
import gspread
import asyncio

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.types import Message, BotCommand
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from aiohttp import web

# Переменные окружения
TOKEN = os.getenv("TOKEN")
GOOGLE_CREDS = os.getenv("GOOGLE_CREDS")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(GOOGLE_CREDS)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1

# Инициализация бота
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Установка команд
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="total", description="Посмотреть расходы за день"),
        BotCommand(command="debug", description="Отладка"),
    ]
    await bot.set_my_commands(commands)

# Хендлеры
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
    date_col = header.index("Дата")
    amount_col = header.index("Сумма")
    total = sum(int(row[amount_col]) for row in records[1:] if row[date_col] == today)
    await message.answer(f"\U0001F4B0 Итог за {today}: {total} руб.")

@router.message(Command("debug"))
async def cmd_debug(message: Message):
    records = sheet.get_all_values()
    await message.answer(f"\U0001F50D Данные в таблице:\n{records if records else 'пусто'}")

@router.message()
async def add_expense(message: Message):
    try:
        data = message.text.split(" ", 1)
        amount = int(data[0])
        category = data[1] if len(data) > 1 else "Прочее"
        date = datetime.now().strftime("%Y-%m-%d")
        sheet.append_row([date, amount, category])
        await message.answer(f"\u2705 Записано: {amount} руб. на {category} ({date})")
    except ValueError:
        await message.answer("Ошибка! Отправь в формате: 500 Еда")
    except Exception as e:
        logging.error(e)
        await message.answer("Ошибка при записи")

# Обработчик вебхука
async def telegram_webhook(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    # Обработка ping-запроса
    if data.get("ping") == "true":
        return web.json_response({"status": "ok", "message": "pong"})

    # Обычное обновление
    await dp.feed_raw_update(bot=bot, update=data, 
                              update_type=data.get("update_type", "message"))
    return web.Response(status=200)

# Aiohttp приложение
app = web.Application()
app.router.add_post(f"/webhook/{WEBHOOK_SECRET}", telegram_webhook)
app.router.add_get("/", lambda request: web.Response(text="pong"))

app.on_startup.append(lambda app: set_commands(bot))
app.on_shutdown.append(lambda app: bot.session.close())

# Запуск
if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))