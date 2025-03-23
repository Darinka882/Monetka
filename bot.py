import logging
import gspread
import os
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from oauth2client.service_account import ServiceAccountCredentials
from aiohttp import web

# Переменные окружения
TOKEN = os.getenv("TOKEN")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

# Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.getenv("GOOGLE_CREDS")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
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
async def cmd_start(message: types.Message):
    await message.answer("Привет! Отправь сумму и категорию расхода. Например: 500 Еда")

@router.message(Command("total"))
async def cmd_total(message: types.Message):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        records = sheet.get_all_values()
        header = records[0]

        if "Дата" not in header or "Сумма" not in header:
            await message.answer("Ошибка: в таблице нет колонок 'Дата' или 'Сумма'.")
            return
        
        date_col = header.index("Дата")
        amount_col = header.index("Сумма")

        total = sum(
            int(row[amount_col])
            for row in records[1:]
            if len(row) > max(date_col, amount_col) and row[date_col] == today
        )

        await message.answer(f"💰 Итог за {today}: {total} руб.")
    except Exception as e:
        logging.error(e)
        await message.answer("Ошибка при подсчете суммы.")

@router.message(Command("debug"))
async def cmd_debug(message: types.Message):
    try:
        records = sheet.get_all_values()
        await message.answer(f"🔍 Данные в таблице:\n{records}")
    except Exception as e:
        logging.error(e)
        await message.answer("Ошибка при чтении таблицы.")

@router.message()
async def add_expense(message: types.Message):
    try:
        data = message.text.split(" ", 1)
        amount = int(data[0])
        category = data[1] if len(data) > 1 else "Прочее"
        date = datetime.now().strftime("%Y-%m-%d")

        sheet.append_row([date, amount, category])
        await message.answer(f"✅ Записано: {amount} руб. на {category} ({date})")
    except Exception as e:
        logging.error(e)
        await message.answer("Ошибка при добавлении расхода. Убедись в формате: 500 Еда")

dp.include_router(router)

async def on_startup(bot: Bot):
    await set_commands(bot)

async def main():
    app = web.Application()
    dp.startup.register(on_startup)

    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET)
    webhook_handler.register(app, path=f"/webhook/{WEBHOOK_SECRET}")
    setup_application(app, dp, bot=bot)
    return app

if __name__ == "__main__":
    import asyncio
    import uvloop
    uvloop.install()
    asyncio.run(main())
