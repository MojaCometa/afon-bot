import asyncio
import logging
from datetime import datetime, timedelta

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
from dotenv import load_dotenv
import os

load_dotenv()

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
admin_selected_worker = {}

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
    keyboard=[
        [KeyboardButton(text="▶️ Почати день")],
        [KeyboardButton(text="📂 Мої процеси")],
        [KeyboardButton(text="📊 Моя статистика")],
    ],
    resize_keyboard=True,
)

period_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Сьогодні")],
        [KeyboardButton(text="📆 Тиждень")],
        [KeyboardButton(text="🗓 Місяць")],
        [KeyboardButton(text="📊 3 Місяці")],
        [KeyboardButton(text="⬅️ Назад")],
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
        [KeyboardButton(text="📈 Статистика працівника")],
    ],
    resize_keyboard=True,
)


async def get_active_process(user_id):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT process_name, amount
            FROM processes
            WHERE telegram_id = ?
            AND active = 1
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

@dp.message(F.text == "🔄 Змінити процес")
async def change_process(message: Message):

    user_states[message.from_user.id] = "switch_process"

    await my_processes(message)


@dp.message(F.text == "📂 Мої процеси")
async def my_processes(message: Message):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT id, process_name, amount, active
            FROM processes
            WHERE telegram_id = ?
            ORDER BY id ASC
            """,
            (message.from_user.id,),
        )

        processes = await cursor.fetchall()

    if not processes:
        await message.answer("❌ У тебе ще немає процесів")
        return

    text = "📂 <b>Твої процеси:</b>\n\n"

    for index, process in enumerate(processes, start=1):

        status = "🟢" if process[3] == 1 else "⚪"

        text += (
            f"{status} <b>{index}.</b> {process[1]}\n"
            f"🔢 {process[2]} шт\n\n"
        )

    text += (
        "✍️ Напиши номер процесу для переключення\n"
        "або введи нову назву для створення нового процесу"
    )

    user_states[message.from_user.id] = "switch_process"

    await message.answer(text)


@dp.message(F.text == "📊 Моя статистика")
async def stats(message: Message):

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT process_name, amount, date
            FROM history
            WHERE telegram_id = ?
            ORDER BY id DESC
            """,
            (message.from_user.id,),
        )

        rows = await cursor.fetchall()

    if not rows:
        await message.answer("❌ Статистика порожня")
        return

    grouped = {}

    for row in rows:

        process_name = row[0]
        amount = row[1]
        date = row[2]

        if date not in grouped:
            grouped[date] = []

        grouped[date].append(
            f"📌 {process_name} — {amount} шт"
        )

    text = "📊 <b>Твоя статистика:</b>\n\n"

    for date, processes in grouped.items():

        text += f"📅 <b>{date}</b>\n"

        for process in processes:
            text += f"{process}\n"

        text += "\n"

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


@dp.message(F.text == "📈 Статистика працівника")
async def choose_worker(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB_NAME) as db:

        cursor = await db.execute(
            """
            SELECT DISTINCT full_name
            FROM workers
            ORDER BY full_name
            """
        )

        workers = await cursor.fetchall()

    if not workers:
        await message.answer("❌ Працівників не знайдено")
        return

    text = "👤 <b>Вибери працівника:</b>\n\n"

    for index, worker in enumerate(workers, start=1):

        text += f"{index}. {worker[0]}\n"

    text += "\n✍️ Напиши номер працівника"

    admin_selected_worker["workers"] = workers

    user_states[message.from_user.id] = "choose_worker"

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

    # ------------------------
    # Створення нового процесу
    # ------------------------

    if user_states.get(user_id) == "waiting_process":

        async with aiosqlite.connect(DB_NAME) as db:

            await db.execute(
                """
                UPDATE processes
                SET active = 0
                WHERE telegram_id = ?
                """,
                (user_id,),
            )

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

            await db.commit()

        user_states.pop(user_id)

        await message.answer(
            f"✅ Процес <b>{text}</b> створено\n\n"
            f"🔢 Виконано: 0",
            reply_markup=counter_keyboard,
        )

        return


    # ------------------------
    # Вибір працівника адміном
    # ------------------------

    if (
        user_states.get(user_id) == "choose_worker"
        and user_id == ADMIN_ID
    ):

        workers = admin_selected_worker.get("workers", [])

        if not text.isdigit():

            await message.answer(
                "❌ Введи номер працівника"
            )

            return

        number = int(text)

        if number < 1 or number > len(workers):

            text_message = (
                "❌ Працівника не знайдено\n\n"
                "👤 <b>Список працівників:</b>\n\n"
            )

            for index, worker in enumerate(workers, start=1):

                text_message += f"{index}. {worker[0]}\n"

            text_message += "\n✍️ Напиши номер працівника"

            await message.answer(text_message)

            return

        worker_name = workers[number - 1][0]

        admin_selected_worker[user_id] = worker_name

        user_states[user_id] = "choose_period"

        await message.answer(
            f"👤 Працівник: <b>{worker_name}</b>\n\n"
            f"📅 Вибери період:",
            reply_markup=period_keyboard,
        )

        return
    
    # ------------------------
    # Статистика працівника
    # ------------------------

    if (
        user_states.get(user_id) == "choose_period"
        and user_id == ADMIN_ID
    ):

        worker_name = admin_selected_worker.get(user_id)

        if not worker_name:
            return

        days = 1

        if text == "📅 Сьогодні":
            days = 1

        elif text == "📆 Тиждень":
            days = 7

        elif text == "🗓 Місяць":
            days = 30

        elif text == "📊 3 Місяці":
            days = 90

        elif text == "⬅️ Назад":

            user_states.pop(user_id, None)

            await message.answer(
                "🔙 Повернення в адмін меню",
                reply_markup=admin_keyboard,
            )

            return

        else:
            return

        start_date = (
            datetime.now() - timedelta(days=days)
        ).strftime("%d.%m.%Y")

        async with aiosqlite.connect(DB_NAME) as db:

            cursor = await db.execute(
                """
                SELECT history.date,
                       history.process_name,
                       history.amount
                FROM history
                JOIN workers
                ON workers.telegram_id = history.telegram_id
                WHERE workers.full_name = ?
                ORDER BY history.id DESC
                """,
                (worker_name,),
            )

            rows = await cursor.fetchall()

        filtered_rows = []

        now = datetime.now()

        for row in rows:

            row_date = row[0]

            try:

                row_datetime = datetime.strptime(
                    row_date,
                    "%d.%m.%Y"
                )

                difference = now - row_datetime

                # Сьогодні
                if days == 1:

                    if difference.days == 0:
                        filtered_rows.append(row)

                # Тиждень / місяць / 3 місяці
                else:

                    if difference.days <= days:
                        filtered_rows.append(row)

            except:
                continue

        if not filtered_rows:

            await message.answer(
                "❌ За цей період статистики немає"
            )

            return

        text_message = (
            f"📈 <b>Статистика працівника</b>\n"
            f"👤 {worker_name}\n\n"
        )

        grouped = {}

        for row in filtered_rows:

            date = row[0]
            process_name = row[1]
            amount = row[2]

            if date not in grouped:
                grouped[date] = []

            grouped[date].append(
                f"📌 {process_name} — {amount} шт"
            )

        for date, processes in grouped.items():

            text_message += f"📅 <b>{date}</b>\n"

            for process in processes:
                text_message += process + "\n"

            text_message += "\n"


            await message.answer(
               text_message,
               reply_markup=period_keyboard,
)

        return
    


    # ------------------------
    # Назад в адмін меню
    # ------------------------

    if (
        text == "⬅️ Назад"
        and user_id == ADMIN_ID
    ):

        user_states.pop(user_id, None)

        await message.answer(
            "🔙 Повернення в адмін меню",
            reply_markup=admin_keyboard,
        )

        return
    

    # ------------------------
    # Переключення процесу
    # ------------------------

    if user_states.get(user_id) == "switch_process":

        async with aiosqlite.connect(DB_NAME) as db:

            cursor = await db.execute(
                """
                SELECT id, process_name, amount, active
                FROM processes
                WHERE telegram_id = ?
                ORDER BY id ASC
                """,
                (user_id,),
            )

            all_processes = await cursor.fetchall()

            selected_process = None

            # Якщо введено номер
            if text.isdigit():

                number = int(text)

                if 1 <= number <= len(all_processes):
                    selected_process = all_processes[number - 1]

                else:

                    text_message = "❌ Процес не знайдено\n\n"
                    text_message += "📂 <b>Твої процеси:</b>\n\n"

                    for index, process in enumerate(all_processes, start=1):

                        status = "🟢" if process[3] == 1 else "⚪"

                        text_message += (
                            f"{status} <b>{index}.</b> {process[1]}\n"
                            f"🔢 {process[2]} шт\n\n"
                        )

                    text_message += (
                        "✍️ Напиши номер процесу\n"
                        "або введи нову назву"
                    )

                    await message.answer(text_message)

                    return

            # Якщо введено назву
            else:

                for process in all_processes:

                    if process[1].lower() == text.lower():

                        selected_process = process
                        break

            # Якщо процес знайдено
            if selected_process:

                await db.execute(
                    """
                    UPDATE processes
                    SET active = 0
                    WHERE telegram_id = ?
                    """,
                    (user_id,),
                )

                await db.execute(
                    """
                    UPDATE processes
                    SET active = 1
                    WHERE id = ?
                    """,
                    (selected_process[0],),
                )

                await db.commit()

                user_states.pop(user_id, None)

                await message.answer(
                    f"🔄 Активний процес:\n\n"
                    f"📌 <b>{selected_process[1]}</b>\n"
                    f"🔢 {selected_process[2]} шт",
                    reply_markup=counter_keyboard,
                )

                return

            # Якщо введено нову назву процесу
            await db.execute(
                """
                UPDATE processes
                SET active = 0
                WHERE telegram_id = ?
                """,
                (user_id,),
            )

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

            await db.commit()

            user_states.pop(user_id, None)

            await message.answer(
                f"✅ Новий процес створено:\n\n"
                f"📌 <b>{text}</b>\n"
                f"🔢 0 шт",
                reply_markup=counter_keyboard,
            )

            return

    # ------------------------
    # Інша сума
    # ------------------------

   

   
    # ------------------------
    # Кнопки +1 +5 +10
    # ------------------------

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
            f"📌 {process_name}\n"
            f"🔢 {new_amount} шт",
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
