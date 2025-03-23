import logging
import gspread
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, BotCommand
from aiogram.enums import ParseMode
from aiogram.filters import Command
import asyncio
from aiogram.client.default import DefaultBotProperties
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# Настройки бота
TOKEN = "7584649281:AAFa5ydURl_MLA6zNO-Q4ObH_vG3FXJDcsk"
SPREADSHEET_ID = "1EhlhX89B36F4cdTORWKkLteH-IFQncinlhFGYnepQQw"

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Подключение к Google Таблице
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# Инициализация бота
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

async def set_commands(bot: Bot):
    """Устанавливает командное меню в Telegram"""
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
    """Подсчет трат за сегодня и запись итога в таблицу"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        records = sheet.get_all_values()  # Получаем все строки
        header = records[0]  # Заголовки столбцов

        # Проверяем наличие нужных столбцов
        if "Дата" not in header or "Сумма" not in header:
            await message.answer("Ошибка: в таблице нет колонок 'Дата' или 'Сумма'.")
            return
        
        date_col = header.index("Дата") + 1
        amount_col = header.index("Сумма") + 1
        total_col = header.index("Итог") + 1 if "Итог" in header else None

        total = sum(int(row[amount_col - 1]) for row in records[1:] if row[date_col - 1] == today)

        # Записываем итог в таблицу
        if total_col:
            sheet.update_cell(len(records) + 1, total_col, total)  # Записываем в первую свободную строку

        await message.answer(f"💰 Итог за {today}: {total} руб.")
    except Exception as e:
        await message.answer("Ошибка при подсчете суммы.")
        logging.error(e)

@router.message(Command("debug"))
async def debug(message: Message):
    """Команда для проверки данных в таблице"""
    try:
        records = sheet.get_all_values()  # Получаем все строки
        if not records:
            await message.answer("Таблица пустая.")
            return
        await message.answer(f"🔍 Данные в таблице:\n{records}")
    except Exception as e:
        await message.answer("Ошибка при чтении таблицы.")
        logging.error(e)

@router.message()
async def add_expense(message: Message):
    """Добавление расхода в таблицу"""
    try:
        data = message.text.split(" ", 1)
        amount = int(data[0])  # Сумма
        category = data[1] if len(data) > 1 else "Прочее"  # Категория
        date = datetime.now().strftime("%Y-%m-%d")  # Текущая дата

        sheet.append_row([date, amount, category])  # Запись в Google Таблицу
        await message.answer(f"✅ Записано: {amount} руб. на {category} ({date})")
    except ValueError:
        await message.answer("Ошибка! Отправь сообщение в формате: 500 Еда")
    except Exception as e:
        await message.answer("Произошла ошибка при записи.")
        logging.error(e)

async def main():
    """Основная функция запуска бота"""
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands(bot)  # Устанавливаем командное меню
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())