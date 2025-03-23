import logging
import gspread
import asyncio
import os
import json
from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.types import Message, BotCommand
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from aiohttp import web

# Настройки
TOKEN = os.getenv("TOKEN")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
BASE_WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook/{WEBHOOK_SECRET}"

# Логирование
logging.basicConfig(level=logging.INFO)

# Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.getenv("GOOGLE_CREDS")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# Bot init
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="total", description="Посмотреть расходы за день"),
        BotCommand(command="debug", description="Отладка"),
    ]
    await bot.set_my_commands(commands)

@router.message(Command("start"))
async def start(message: Message):
    await message.answer("Привет! Отправь сумму и категорию расхода. Например: 500 Еда")

@router.message(Command("total"))
async def get_total(message: Message):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        records = sheet.get_all_values()
        header = records[0]
        if "Дата" not in header or "Сумма" not in header:
            await message.answer("Ошибка: нет колонок 'Дата' или 'Сумма'.")
            return
        date_col = header.index("Дата") + 1
        amount_col = header.index("Сумма") + 1
        total_col = header.index("Итог") + 1 if "Итог" in header else None
        total = sum(int(row[amount_col - 1]) for row in records[1:] if row[date_col - 1] == today)
        if total_col:
            sheet.update_cell(len(records) + 1, total_col, total)
        await message.answer(f"💰 Итог за {today}: {total} руб.")
    except Exception as e:
        await message.answer("Ошибка при подсчете.")
        logging.error(e)

@router.message(Command("debug"))
async def debug(message: Message):
    try:
        records = sheet.get_all_values()
        if not records:
            await message.answer("Таблица пустая.")
            return
        await message.answer(f"🔍 Данные в таблице:\n{records}")
    except Exception as e:
        await message.answer("Ошибка при чтении.")
        logging.error(e)

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
        await message.answer("Формат: 500 Еда")
    except Exception as e:
        await message.answer("Ошибка при записи.")
        logging.error(e)

dp.include_router(router)

# aiohttp-приложение для вебхука
app = web.Application()
dp.startup.register(set_commands)
dp.startup.register(lambda _: bot.set_webhook(BASE_WEBHOOK_URL, secret_token=WEBHOOK_SECRET))
app.router.add_route("*", f"/webhook/{WEBHOOK_SECRET}", dp.webhook_request_handler())
