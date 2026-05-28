import asyncio
import logging
from datetime import datetime

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

TOKEN = "8650993073:AAGuX5PAE9idWp9RDHGbYCOO8RU-LDuIdmQ"
ADMIN_ID = 755891182

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

DB_NAME = "database.db"

user_states = {}


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            telegram_id INTEGER PRIMARY KEY,
            full_name TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS processes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            process_name TEXT,
            amount INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            full_name TEXT,
            process_name TEXT,
            amount INTEGER,
            date TEXT
        )
        """)

        await db.commit()


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="▶️ Почати день")],
        [KeyboardButton(text="📂 Мої процеси")],
        [KeyboardButton(text="📊 Моя статистика")],
    ],
    resize_keyboard=True,
)

counter_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="+1"), KeyboardButton(text="-1")],
        [KeyboardButton(text="+5"), KeyboardButton(text="-5")],
        [KeyboardButton(text="+10"), KeyboardButton(text="-10")],
        [KeyboardButton(text="✍️ Інша сума")],
        [KeyboardButton(text="🔄 Змінити процес")],
        [KeyboardButton(text="🏁 Завершити день")],
        [KeyboardButton(text="⬅️ Головне меню")],
    ],
    resize_keyboard=True,
)
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👥 Активні працівники")],
        [KeyboardButton(text="📅 Історія за місяць")],
    ],
    resize_keyboard=True,
)


async def get_active_process(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT process_name, amount
            FROM processes
            WHERE telegram_id = ? AND active = 1
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        )

        return await cursor.fetchone()


@dp.message(CommandStart())
async def start(message: Message):

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO workers VALUES (?, ?)",
            (message.from_user.id, message.from_user.full_name),
        )
        await db.commit()

    text = (
        f"👋 Вітаю, <b>{message.from_user.full_name}</b>\n\n"
        f"Ласкаво просимо у систему обліку afon"
    )

    if message.from_user.id == ADMIN_ID:
        await message.answer(text, reply_markup=admin_keyboard)
    else:
        await message.answer(text, reply_markup=main_keyboard)


@dp.message(F.text == "▶️ Почати день")
async def start_day(message: Message):
    user_states[message.from_user.id] = "waiting_process"

    await message.answer(
        "📝 Напиши назву нового процесу\n\n"
        "Наприклад:\n"
        "• Наклейки\n"
        "• Білетики\n"
        "• Пайка"
    )


@dp.message(F.text == "📂 Мої процеси")
async def my_processes(message: Message):

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT process_name, amount
            FROM processes
            WHERE telegram_id = ?
            ORDER BY id DESC
            """,
            (message.from_user.id,),
        )

        processes = await cursor.fetchall()

    if not processes:
        await message.answer("❌ У тебе ще немає процесів")
        return

    text = "📂 <b>Твої процеси:</b>\n\n"

    for process in processes:
        text += f"📌 {process[0]} — {process[1]} шт\n"

    text += "\nНапиши назву процесу щоб переключитися на нього"

    user_states[message.from_user.id] = "switch_process"

    await message.answer(text)


@dp.message(F.text == "📊 Моя статистика")
async def stats(message: Message):

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT process_name, amount
            FROM processes
            WHERE telegram_id = ?
            """,
            (message.from_user.id,),
        )

        rows = await cursor.fetchall()

    if not rows:
        await message.answer("❌ Статистика порожня")
        return

    total = sum(row[1] for row in rows)

    text = "📊 <b>Твоя статистика:</b>\n\n"

    for row in rows:
        text += f"📌 {row[0]} — {row[1]}\n"

    text += f"\n🔢 Загалом: <b>{total}</b>"

    await message.answer(text)


@dp.message(F.text == "👥 Активні працівники")
async def admin_active(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT workers.full_name,
                   processes.process_name,
                   processes.amount
            FROM processes
            JOIN workers
            ON workers.telegram_id = processes.telegram_id
            WHERE processes.active = 1
            """
        )

        rows = await cursor.fetchall()

    if not rows:
        await message.answer("❌ Немає активних працівників")
        return

    text = "👥 <b>Активні працівники:</b>\n\n"

    for row in rows:
        text += (
            f"👤 {row[0]}\n"
            f"📌 {row[1]}\n"
            f"🔢 {row[2]} шт\n\n"
        )

    await message.answer(text)


@dp.message(F.text == "📅 Історія за місяць")
async def admin_history(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT full_name,
                   process_name,
                   amount,
                   date
            FROM history
            ORDER BY id DESC
            LIMIT 100
            """
        )

        rows = await cursor.fetchall()

    if not rows:
        await message.answer("❌ Історія порожня")
        return

    text = "📅 <b>Історія:</b>\n\n"

    for row in rows:
        text += (
            f"👤 {row[0]}\n"
            f"📌 {row[1]}\n"
            f"🔢 {row[2]} шт\n"
            f"📆 {row[3]}\n\n"
        )

    await message.answer(text)


@dp.message()
async def all_messages(message: Message):

    user_id = message.from_user.id
    text = message.text

    if user_states.get(user_id) == "waiting_process":

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                """
                INSERT INTO processes (
                    telegram_id,
                    process_name,
                    amount,
                    active,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    text,
                    0,
                    1,
                    str(datetime.now()),
                ),
            )

            await db.execute(
                "UPDATE processes SET active = 0 WHERE telegram_id = ?",
                (user_id,),
            )

            await db.execute(
                """
                UPDATE processes
                SET active = 1
                WHERE id = (
                    SELECT MAX(id)
                    FROM processes
                    WHERE telegram_id = ?
                )
                """,
                (user_id,),
            )

            await db.commit()
            user_states.pop(user_id)

        await message.answer(
            f"✅ Процес <b>{text}</b> створено\n\n"
            f"🔢 Виконано: 0",
            reply_markup=counter_keyboard,
        )

        return

    if user_states.get(user_id) == "switch_process":

        async with aiosqlite.connect(DB_NAME) as db:

            cursor = await db.execute(
                """
                SELECT id
                FROM processes
                WHERE telegram_id = ?
                AND process_name = ?
                """,
                (user_id, text),
            )

            process = await cursor.fetchone()

            if not process:
                await message.answer("❌ Процес не знайдено")
                return

            await db.execute(
                "UPDATE processes SET active = 0 WHERE telegram_id = ?",
                (user_id,),
            )

            await db.execute(
                "UPDATE processes SET active = 1 WHERE id = ?",
                (process[0],),
            )

            await db.commit()

        user_states.pop(user_id)

        active = await get_active_process(user_id)

        await message.answer(
            f"🔄 Активний процес: <b>{active[0]}</b>\n"
            f"🔢 Виконано: {active[1]}",
            reply_markup=counter_keyboard,
        )

        return

    if text == "⬅️ Головне меню":
        await message.answer("🏠 Головне меню", reply_markup=main_keyboard)
        return

    if text == "🔄 Змінити процес":
        await my_processes(message)
        return

    active = await get_active_process(user_id)

    if not active:
        return

    process_name, amount = active

    if text in ["+1", "-1", "+5", "-5", "+10", "-10"]:

        value = int(text)
        new_amount = amount + value

        if new_amount < 0:
            new_amount = 0

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                """
                UPDATE processes
                SET amount = ?
                WHERE telegram_id = ?
                AND active = 1
                """,
                (new_amount, user_id),
            )
            await db.commit()

        await message.answer(
            f"📌 Процес: <b>{process_name}</b>\n"
             f"🔢 Виконано: <b>{new_amount}</b>",
            reply_markup=counter_keyboard,
        )

        return

    if text == "✍️ Інша сума":
        user_states[user_id] = "custom_amount"

        await message.answer("✍️ Введи число")
        return

    if user_states.get(user_id) == "custom_amount":

        try:
            value = int(text)
        except:
            await message.answer("❌ Введи число")
            return

        new_amount = amount + value

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                """
                UPDATE processes
                SET amount = ?
                WHERE telegram_id = ?
                AND active = 1
                """,
                (new_amount, user_id),
            )
            await db.commit()

        user_states.pop(user_id)

        await message.answer(
            f"📌 Процес: <b>{process_name}</b>\n"
            f"🔢 Виконано: <b>{new_amount}</b>",
            reply_markup=counter_keyboard,
        )

        return

    if text == "🏁 Завершити день":

        async with aiosqlite.connect(DB_NAME) as db:

            cursor = await db.execute(
                """
                SELECT process_name, amount
                FROM processes
                WHERE telegram_id = ?
                """,
                (user_id,),
            )

            rows = await cursor.fetchall()

            for row in rows:
                await db.execute(
                    """
                    INSERT INTO history (
                        telegram_id,
                        full_name,
                        process_name,
                        amount,
                        date
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        message.from_user.full_name,
                        row[0],
                        row[1],
                        datetime.now().strftime("%d.%m.%Y"),
                    ),
                )

            await db.execute(
                "DELETE FROM processes WHERE telegram_id = ?",
                (user_id,),
            )

            await db.commit()

        await message.answer(
            "🏁 Робочий день завершено\n\n"
            "Дані збережено ✅",
            reply_markup=main_keyboard,
        )


async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())