import os
import json
import logging
import gspread
import uvloop
import asyncio

from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, BotCommand
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# Инициализация uvloop
uvloop.install()

# Переменные окружения
TOKEN = os.getenv("TOKEN")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
GOOGLE_CREDS = os.getenv("GOOGLE_CREDS")

# Подключение к Google Таблице
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(GOOGLE_CREDS)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Команды
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="total", description="Посмотреть расходы за день"),
        BotCommand(command="debug", description="Отладка"),
    ]
    await bot.set_my_commands(commands)

# Хендлеры
@router.message(Command("start"))
async def start(message: Message):
    await message.answer("Привет! Отправь сумму и категорию расхода. Например: 500 Еда")

@router.message(Command("total"))
async def get_total(message: Message):
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
async def debug(message: Message):
    records = sheet.get_all_values()
    await message.answer(f"🔍 Данные в таблице:\n{records if records else 'пусто'}")

@router.message()
async def add_expense(message: Message):
    try:
        data = message.text.split(" ", 1)
        amount = int(data[0])
        category = data[1] if len(data) > 1 else "Прочее"
        date = datetime.now().strftime("%Y-%m-%d")
        sheet.append_row([date, amount, category])
        await message.answer(f"✅ Записано: {amount} руб. на {category} ({date})")
    except ValueError:
        await message.answer("Ошибка! Отправь в формате: 500 Еда")
    except Exception as e:
        logging.error(e)
        await message.answer("Ошибка при записи")

# Обработка ping-запросов
async def ping_handler(request: Request) -> Response:
    try:
        data = await request.json()
        if data.get("ping") == "true":
            return web.json_response({"status": "ok", "message": "pong"})
    except Exception:
        pass  # игнорируем если это не JSON или нет поля ping
    return Response(status=400, text="Bad Request")

# aiohttp-приложение
app = web.Application()
app.router.add_post(f"/webhook/{WEBHOOK_SECRET}", SimpleRequestHandler(dp, bot, secret_token=WEBHOOK_SECRET).handle_request)
app.router.add_post("/", ping_handler)  # для Render ping
app.router.add_get("/", lambda r: Response(text="pong"))

app.on_startup.append(lambda app: bot.delete_webhook(drop_pending_updates=True))
app.on_startup.append(lambda app: set_commands(bot))
app.on_shutdown.append(lambda app: bot.session.close())

# Запуск на Render
if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
