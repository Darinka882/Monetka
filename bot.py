import os
import json
import logging
import gspread
from aiohttp import web
from aiohttp.web_request import Request
from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, BotCommand
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

# Custom handler for Render ping
class CustomRequestHandler(SimpleRequestHandler):
    async def _handle_update(self, request: Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.Response(status=400, text="Invalid JSON")

        # Handle ping from Render
        if data.get("ping") == "true":
            return web.Response(text="pong")

        return await super()._handle_update(request)

# Environment variables
TOKEN = os.getenv("TOKEN")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
GOOGLE_CREDS = os.getenv("GOOGLE_CREDS")

# Google Sheets connection
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(GOOGLE_CREDS)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# Logging
logging.basicConfig(level=logging.INFO)

# Bot setup
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Commands
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="total", description="Посмотреть расходы за день"),
        BotCommand(command="debug", description="Отладка"),
    ]
    await bot.set_my_commands(commands)

# Handlers
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

# AIOHTTP web app
app = web.Application()
CustomRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET).register(
    app, path=f"/webhook/{WEBHOOK_SECRET}"
)

# Optional ping route for testing
app.router.add_get("/", lambda r: web.Response(text="pong"))

app.on_startup.append(lambda app: bot.delete_webhook(drop_pending_updates=True))
app.on_startup.append(lambda app: set_commands(bot))
app.on_shutdown.append(lambda app: bot.session.close())

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))