
import asyncio
import logging
import aiosqlite
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Конфигурация
BOT_TOKEN = "8374588436:AAHI2l-IlioRcD1DT1bjBUv3GoYT-WCQdrw"
ADMIN_ID = 8218782038  # Замените на ваш Telegram ID (узнать можно у @userinfobot)
DB_NAME = "bookings.db"

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния для FSM
class BookingStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_date = State()
    waiting_for_time = State()

# Создание базы данных
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                name TEXT,
                date TEXT,
                time TEXT,
                user_id INTEGER
            )
        ''')
        await db.commit()

# Главная клавиатура
def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Записаться")],
            [KeyboardButton(text="📋 Посмотреть записи")],
            [KeyboardButton(text="❌ Отменить запись")]
        ],
        resize_keyboard=True
    )
    return keyboard

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Добро пожаловать! 👋\n\n"
        "Выберите действие:",
        reply_markup=get_main_keyboard()
    )

# Обработчик команды /clients (только для админа)
@dp.message(Command("clients"))
async def cmd_clients(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет доступа к этой команде.")
        return
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM bookings ORDER BY date, time") as cursor:
            bookings = await cursor.fetchall()
    
    if not bookings:
        await message.answer("База данных пустая.")
        return
    
    text = "📊 Все записи в базе:\n\n"
    for booking in bookings:
        text += f"ID: {booking[0]}\n"
        text += f"Username: @{booking[1] or 'не указан'}\n"
        text += f"Имя: {booking[2]}\n"
        text += f"Дата: {booking[3]}\n"
        text += f"Время: {booking[4]}\n"
        text += f"User ID: {booking[5]}\n"
        text += "─────────────\n"
    
    await message.answer(text)

# Обработчик команды /clear (только для админа)
@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет доступа к этой команде.")
        return
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM bookings")
        await db.commit()
    
    await message.answer("✅ База данных очищена.")

# Обработчик кнопки "Записаться"
@dp.message(F.text == "📝 Записаться")
async def process_booking_request(message: types.Message, state: FSMContext):
    await message.answer("Как вас зовут?")
    await state.set_state(BookingStates.waiting_for_name)

# Обработчик ввода имени
@dp.message(StateFilter(BookingStates.waiting_for_name))
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите дату записи (в формате ДД.ММ.ГГГГ):")
    await state.set_state(BookingStates.waiting_for_date)

# Обработчик ввода даты
@dp.message(StateFilter(BookingStates.waiting_for_date))
async def process_date(message: types.Message, state: FSMContext):
    try:
        # Проверяем формат даты
        date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        
        # Проверяем, что дата не в прошлом
        if date_obj.date() < datetime.now().date():
            await message.answer("❌ Нельзя записаться на прошедшую дату. Введите корректную дату:")
            return
        
        await state.update_data(date=message.text)
        await message.answer("Введите время записи (в формате ЧЧ:ММ):")
        await state.set_state(BookingStates.waiting_for_time)
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ (например, 25.12.2023):")

# Обработчик ввода времени
@dp.message(StateFilter(BookingStates.waiting_for_time))
async def process_time(message: types.Message, state: FSMContext):
    try:
        # Проверяем формат времени
        time_obj = datetime.strptime(message.text, "%H:%M")
        
        data = await state.get_data()
        
        # Сохраняем в базу данных
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO bookings (username, name, date, time, user_id) VALUES (?, ?, ?, ?, ?)",
                (message.from_user.username, data['name'], data['date'], message.text, message.from_user.id)
            )
            await db.commit()
        
        await message.answer(
            f"✅ Запись успешно создана!\n\n"
            f"👤 Имя: {data['name']}\n"
            f"📅 Дата: {data['date']}\n"
            f"🕐 Время: {message.text}",
            reply_markup=get_main_keyboard()
        )
        
        await state.clear()
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте формат ЧЧ:ММ (например, 14:30):")

# Обработчик кнопки "Посмотреть записи"
@dp.message(F.text == "📋 Посмотреть записи")
async def view_bookings(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT * FROM bookings WHERE user_id = ? ORDER BY date, time",
            (message.from_user.id,)
        ) as cursor:
            bookings = await cursor.fetchall()
    
    if not bookings:
        await message.answer("У вас нет активных записей.")
        return
    
    text = "📋 Ваши записи:\n\n"
    for booking in bookings:
        text += f"👤 Имя: {booking[2]}\n"
        text += f"📅 Дата: {booking[3]}\n"
        text += f"🕐 Время: {booking[4]}\n"
        text += "─────────────\n"
    
    await message.answer(text)

# Обработчик кнопки "Отменить запись"
@dp.message(F.text == "❌ Отменить запись")
async def cancel_booking_menu(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT * FROM bookings WHERE user_id = ? ORDER BY date, time",
            (message.from_user.id,)
        ) as cursor:
            bookings = await cursor.fetchall()
    
    if not bookings:
        await message.answer("У вас нет записей для отмены.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for booking in bookings:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{booking[2]} - {booking[3]} {booking[4]}",
                callback_data=f"cancel_{booking[0]}"
            )
        ])
    
    await message.answer("Выберите запись для отмены:", reply_markup=keyboard)

# Обработчик отмены записи
@dp.callback_query(F.data.startswith("cancel_"))
async def process_cancel_booking(callback: types.CallbackQuery):
    booking_id = int(callback.data.split("_")[1])
    
    async with aiosqlite.connect(DB_NAME) as db:
        # Проверяем, что запись принадлежит пользователю
        async with db.execute(
            "SELECT * FROM bookings WHERE id = ? AND user_id = ?",
            (booking_id, callback.from_user.id)
        ) as cursor:
            booking = await cursor.fetchone()
        
        if booking:
            await db.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
            await db.commit()
            
            await callback.message.edit_text(
                f"✅ Запись отменена:\n"
                f"👤 Имя: {booking[2]}\n"
                f"📅 Дата: {booking[3]}\n"
                f"🕐 Время: {booking[4]}"
            )
        else:
            await callback.answer("Запись не найдена.", show_alert=True)
    
    await callback.answer()

# Обработчик неизвестных сообщений
@dp.message()
async def unknown_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer(
            "Не понимаю вас. Используйте кнопки меню.",
            reply_markup=get_main_keyboard()
        )

async def main():
    # Инициализация базы данных
    await init_db()
    
    # Запуск бота
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
