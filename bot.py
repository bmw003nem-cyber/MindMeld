import asyncio
import json
import os
from datetime import date

from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

import config  # наш файл с текстами/ссылками

# --------- Базовая инициализация ----------
bot = Bot(token=config.BOT_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)

# --------- Клавиатуры ----------
def main_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🧠 Вопрос дня"), KeyboardButton("🔔 Подписаться на рассылку"))
    kb.row(KeyboardButton("📄 Отзывы"), KeyboardButton("📂 Гайды"))
    kb.row(KeyboardButton("📕 Наставничество"), KeyboardButton("📌 Консультация"))
    kb.add(KeyboardButton("💛 Поддержать"))
    return kb

def back_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("⬅️ Назад"))

def mentorship_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✍️ Оставить заявку", url=config.MENTORSHIP_LINK))
    return kb

def consultation_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✍️ Оставить заявку", url=config.CONSULTATION_LINK))
    return kb

def reviews_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📌 Пост с отзывами", url=config.REVIEWS_LINK))
    kb.add(InlineKeyboardButton("💬 Чат с отзывами", url=config.REVIEWS_CHAT))
    return kb

# --------- Вопрос дня ----------
def _load_insights() -> list:
    """
    Возвращает список «вопросов дня».
    Поддерживает:
      - ["строка", ...]
      - [{"question": "...", "options": ["...","..."]}, ...]
      - [{"q": "...", "answers": ["..."]}, ...]
    """
    path = os.path.join(os.getcwd(), "insights.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []

def get_today_question() -> dict:
    """
    Возвращает словарь вида:
      {"text": "...", "options": ["...","...", ...]}  # options может отсутствовать
    """
    items = _load_insights()
    if not items:
        return {"text": "Вопрос дня готовится. Загляни чуть позже 🙌"}

    idx = date.today().toordinal() % len(items)
    item = items[idx]

    # разные форматы на всякий случай
    if isinstance(item, str):
        return {"text": item}

    if isinstance(item, dict):
        text = item.get("question") or item.get("q") or item.get("text")
        opts = item.get("options") or item.get("answers") or []
        if isinstance(opts, list) and all(isinstance(x, str) for x in opts):
            return {"text": text or "Вопрос дня", "options": opts}
        return {"text": text or "Вопрос дня"}

    return {"text": "Вопрос дня"}

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer(config.WELCOME_MESSAGE, reply_markup=main_kb())

# --------- Роутинг по меню ----------
@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def go_back(message: types.Message):
    await message.answer("Главное меню:", reply_markup=main_kb())

@dp.message_handler(lambda m: m.text == "📕 Наставничество")
async def mentorship(message: types.Message):
    await message.answer(config.MENTORSHIP_TEXT, reply_markup=back_kb())
    await message.answer("Если откликается — жми кнопку ниже:", reply_markup=types.ReplyKeyboardRemove())
    await message.answer(" ", reply_markup=back_kb())  # оставить «Назад» на экране
    await message.answer(" ", reply_markup=types.ReplyKeyboardRemove())
    await message.answer("✍️ Оставить заявку", reply_markup=types.ReplyKeyboardRemove())
    await message.answer(" ", reply_markup=types.ReplyKeyboardRemove())

    # Кнопка‑ссылка отдельным сообщением
    await message.answer("Перейти к заявке:", reply_markup=types.ReplyKeyboardRemove())
    await message.answer(" ", reply_markup=types.ReplyKeyboardRemove())
    await message.answer(" ", reply_markup=types.ReplyKeyboardRemove())
    await bot.send_message(message.chat.id, "✍️ Заявка", reply_markup=consultation_kb())
    await message.answer(" ", reply_markup=back_kb())

@dp.message_handler(lambda m: m.text == "📌 Консультация")
async def consultation(message: types.Message):
    await message.answer(config.CONSULTATION_TEXT, reply_markup=back_kb())
    await bot.send_message(message.chat.id, "✍️ Оставить заявку", reply_markup=consultation_kb())

@dp.message_handler(lambda m: m.text == "📄 Отзывы")
async def reviews(message: types.Message):
    await message.answer("Выбери, что открыть:", reply_markup=back_kb())
    await bot.send_message(message.chat.id, "Отзывы:", reply_markup=reviews_kb())

@dp.message_handler(lambda m: m.text == "💛 Поддержать")
async def support(message: types.Message):
    # Пытаемся отправить QR, если файл есть
    qr_path = os.path.join("assets", "donation_qr.png")
    if os.path.exists(qr_path):
        with open(qr_path, "rb") as ph:
            await bot.send_photo(message.chat.id, ph, caption=config.SUPPORT_TEXT)
    else:
        await message.answer(config.SUPPORT_TEXT, reply_markup=back_kb())

@dp.message_handler(lambda m: m.text == "📂 Гайды")
async def guides(message: types.Message):
    text = (
        "Гайды доступны после подписки на канал 🔔\n\n"
        "Нажми «Подписаться на рассылку», а затем возвращайся за своим первым гайдом. "
        "Важно: один гайд на человека."
    )
    await message.answer(text, reply_markup=back_kb())

@dp.message_handler(lambda m: m.text == "🔔 Подписаться на рассылку")
async def subscribe(message: types.Message):
    await message.answer(
        "Канал с инсайтами и анонсами уже рядом 🙂\n\n"
        "Открой: <a href='https://t.me/vse_otvety_vnutri_nas'>t.me/vse_otvety_vnutri_nas</a>\n\n"
        "После подписки вернись за своим гайдом.",
        disable_web_page_preview=True,
        reply_markup=back_kb(),
    )

@dp.message_handler(lambda m: m.text == "🧠 Вопрос дня")
async def ask_question(message: types.Message):
    q = get_today_question()
    txt = f"🧠 <b>Вопрос дня</b>\n\n{q['text']}"
    kb = back_kb()
    # Если есть варианты — показываем их как отдельную клавиатуру строками
    options = q.get("options") or []
    if options:
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        for opt in options:
            kb.add(KeyboardButton(opt))
        kb.add(KeyboardButton("⬅️ Назад"))
    await message.answer(txt, reply_markup=kb)

# --------- Keep-alive web server (Render) ----------
async def _run_health_server():
    """
    Поднимает aiohttp‑сервер на PORT (Render сканирует порт).
    /health -> {"status":"ok"}
    """
    from aiohttp import web

    async def handle_health(_):
        return web.json_response({"status": "ok", "service": "telegram_bot"})

    app = web.Application()
    app.add_routes([web.get("/health", handle_health)])

    port = int(os.getenv("PORT", "10000"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def on_startup(_):
    # Запускаем health‑сервер параллельно с polling
    asyncio.create_task(_run_health_server())

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
