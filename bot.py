# ---------- bot.py (готовая версия под config.py) ----------
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.exceptions import ChatNotFound, BadRequest

import config

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Память в процессе: кого уже порадовали гайдом (без БД)
issued_guide_users = set()

# === КЛАВИАТУРЫ ===
def back_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton(config.BTN_BACK))
    return kb

def main_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton(config.BTN_DAILY),
        KeyboardButton(config.BTN_SUBSCRIBE)
    )
    kb.row(
        KeyboardButton(config.BTN_GUIDES),
        KeyboardButton(config.BTN_MENTORING)
    )
    kb.row(
        KeyboardButton(config.BTN_CONSULT),
        KeyboardButton(config.BTN_SUPPORT)
    )
    kb.row(KeyboardButton(config.BTN_REVIEWS))
    return kb

def check_sub_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton(config.BTN_CHECK_SUB))
    kb.add(KeyboardButton(config.BTN_BACK))
    return kb

# === ПОЛЕЗНЫЕ ФУНКЦИИ ===
async def is_user_subscribed(user_id: int) -> bool:
    """
    Проверка подписки на канал CHANNEL_USERNAME.
    Возвращает True, если пользователь подписан.
    """
    try:
        member = await bot.get_chat_member(chat_id=config.CHANNEL_USERNAME, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except (ChatNotFound, BadRequest):
        # если канал приватный/недоступен по названию — вернётся False
        return False
    except Exception:
        return False

async def send_welcome(message: types.Message):
    """
    Отправка приветствия + главное меню.
    """
    if os.path.exists(config.WELCOME_PHOTO):
        with open(config.WELCOME_PHOTO, "rb") as ph:
            await message.answer_photo(photo=ph, caption=config.WELCOME_MESSAGE, reply_markup=main_kb())
    else:
        await message.answer(config.WELCOME_MESSAGE, reply_markup=main_kb())

# === /start и «Главное меню» ===
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await send_welcome(message)

@dp.message_handler(lambda m: m.text in {config.BTN_MAIN_MENU, "Главное меню", "/menu"})
async def to_main(message: types.Message):
    await send_welcome(message)

# === КОНСУЛЬТАЦИЯ ===
@dp.message_handler(lambda m: m.text == config.BTN_CONSULT)
async def consult(message: types.Message):
    text = config.CONSULT_TEXT
    # Кнопка «Оставить заявку» = просто ссылка на диалог с тобой
    ikb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📝 Оставить заявку", url=f"https://t.me/{config.ADMIN_USERNAME.lstrip('@')}")
    )
    await message.answer(text, reply_markup=back_kb())
    await message.answer("Готов разобрать твой запрос 👇", reply_markup=ikb)

# === НАСТАВНИЧЕСТВО ===
@dp.message_handler(lambda m: m.text == config.BTN_MENTORING)
async def mentoring(message: types.Message):
    await message.answer(config.MENTORING_TEXT, reply_markup=back_kb())

# === ОТЗЫВЫ ===
@dp.message_handler(lambda m: m.text == config.BTN_REVIEWS)
async def reviews(message: types.Message):
    ikb = InlineKeyboardMarkup(row_width=1)
    ikb.add(
        InlineKeyboardButton("📌 Пост с отзывами", url=config.REVIEWS_POST_URL),
        InlineKeyboardButton("💬 Чат/канал с отзывами", url=config.REVIEWS_CHAT_URL),
    )
    await message.answer("Здесь собрал отзывы:", reply_markup=back_kb())
    await message.answer("Выбери:", reply_markup=ikb)

# === ПОДДЕРЖАТЬ ===
@dp.message_handler(lambda m: m.text == config.BTN_SUPPORT)
async def support(message: types.Message):
    # Отправим QR, если лежит в assets
    if os.path.exists(config.DONATION_QR_IMAGE):
        with open(config.DONATION_QR_IMAGE, "rb") as ph:
            await message.answer_photo(ph, caption=config.DONATE_TEXT, reply_markup=back_kb())
    else:
        await message.answer(config.DONATE_TEXT, reply_markup=back_kb())

# === ПОДПИСКА НА РАССЫЛКУ (заглушка) ===
@dp.message_handler(lambda m: m.text == config.BTN_SUBSCRIBE)
async def subscribe_info(message: types.Message):
    await message.answer(
        "🔔 Здесь будет персональная рассылка. Пока просто нажми «Вопрос дня» — и получишь мини‑фокус на сегодня.",
        reply_markup=back_kb()
    )

# === ГАЙДЫ (после подписки) ===
@dp.message_handler(lambda m: m.text == config.BTN_GUIDES)
async def guides_entry(message: types.Message):
    uid = message.from_user.id
    if uid in issued_guide_users:
        await message.answer("Ты уже получил свой гайд сегодня. Возвращайся завтра 😊", reply_markup=back_kb())
        return

    await message.answer(config.GUIDES_NOTICE, reply_markup=check_sub_kb())

@dp.message_handler(lambda m: m.text == config.BTN_CHECK_SUB)
async def guides_check_sub(message: types.Message):
    uid = message.from_user.id
    subscribed = await is_user_subscribed(uid)
    if not subscribed:
        await message.answer(
            f"Похоже, подписки на {config.CHANNEL_USERNAME} ещё нет.\n"
            "Подпишись и жми «Проверить подписку».", reply_markup=check_sub_kb()
        )
        return

    # Подписка есть — выдаём один гайд на выбор (без БД, просто один готовый файл)
    # Здесь можешь расширить: сделать инлайн‑меню выбора из нескольких PDF
    guide_path = "guide_path_to_self.pdf"  # пример: один гайд
    if not os.path.exists(guide_path):
        await message.answer("Файл гайда не найден на сервере. Сообщи мне, я поправлю 🙏", reply_markup=back_kb())
        return

    with open(guide_path, "rb") as f:
        await message.answer_document(f, caption="Твой гайд. Приятной практики! ✨", reply_markup=back_kb())

    issued_guide_users.add(uid)
    await message.answer("Напоминаю: я выдаю <b>один</b> гайд на выбор после подписки. Спасибо за осознанность 🙌")

# === ВОПРОС ДНЯ ===
QUESTION_TEXT = "🧠 Вопрос дня\n\nКакая мысль чаще всего тормозит тебя?\n\nВыбери вариант:"
OPTIONS = [
    "«Я не успею»",
    "«Не идеально — не делать»",
    "«Что скажут другие?»",
    "«Я потом»",
]

@dp.message_handler(lambda m: m.text == config.BTN_DAILY)
async def daily_question(message: types.Message):
    ikb = InlineKeyboardMarkup(row_width=1)
    for i, opt in enumerate(OPTIONS):
        ikb.add(InlineKeyboardButton(opt, callback_data=f"q:{i}"))
    await message.answer(QUESTION_TEXT, reply_markup=ikb)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("q:"))
async def daily_answer(call: types.CallbackQuery):
    idx = int(call.data.split(":")[1])
    choice = OPTIONS[idx]
    tips = {
        0: "Попробуй план на 15–30 минут. Маленький шаг — тоже шаг.",
        1: "Сделай на 70% и отправь. Совершенство — тонна прокрастинации.",
        2: "Сфокусируйся на ценности для себя и близких. Остальные догонят.",
        3: "Назначь конкретное время: «сегодня в 19:00 — 20 минут» и начни.",
    }
    await call.message.answer(
        f"Ты выбрал: <b>{choice}</b>\n\nМаленький фокус на сегодня:\n— {tips.get(idx, 'Действуй коротко и сразу.')}",
        reply_markup=main_kb()
    )
    await call.answer()

# === «НАЗАД» ===
@dp.message_handler(lambda m: m.text == config.BTN_BACK)
async def back(message: types.Message):
    await send_welcome(message)

# === ФОЛЛБЭК ===
@dp.message_handler(content_types=types.ContentTypes.ANY)
async def fallback(message: types.Message):
    # на любое непонятное — даём главное меню
    await message.answer("Выбери действие из меню ниже 👇", reply_markup=main_kb())

# === СТАРТ ===
async def on_startup(dp: Dispatcher):
    # снимаем вебхук, чтобы polling был единственным источником апдейтов
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    # можно добавить ещё и лог «бот запущен»
    # await bot.send_message(config.ADMIN_ID, "✅ Бот запущен")

if __name__ == "__main__":
    # Важно: единственный вызов start_polling
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
