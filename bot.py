# ========================  BOT  ============================
import os
import json
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, InputFile
)
from aiogram.utils import executor

from config import (
    BOT_TOKEN, ADMIN_ID,
    CHANNEL_USERNAME, START_TEXT,
    MENTORING_TEXT, CONSULTATION_TEXT,
    SUPPORT_TEXT, CONTACT_TEXT, SUBSCRIBE_TEXT, QOD_INTRO,
    WELCOME_PHOTO, DONATION_QR,
    GUIDES, REVIEWS_URL, SUBSCRIBE_URL, CONTACT_URL,
    BTN_MENTORING, BTN_CONSULTATION, BTN_GUIDES, BTN_QOD,
    BTN_REVIEWS, BTN_SUPPORT, BTN_CONTACT, BTN_SUBSCRIBE,
    BTN_BACK, BTN_LEAVE_REQUEST,
    SUPPORT_QR_CAPTION
)

# -----------------------------------------------------------
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)

# ======================  КНОПКИ  ===========================

def back_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(BTN_BACK, callback_data="menu"))
    return kb

def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(BTN_QOD, callback_data="qod"),
        InlineKeyboardButton(BTN_SUBSCRIBE, url=SUBSCRIBE_URL),
    )
    kb.add(
        InlineKeyboardButton(BTN_MENTORING, callback_data="mentoring"),
        InlineKeyboardButton(BTN_CONSULTATION, callback_data="consult"),
    )
    kb.add(
        InlineKeyboardButton(BTN_GUIDES, callback_data="guides"),
        InlineKeyboardButton(BTN_REVIEWS, url=REVIEWS_URL),
    )
    kb.add(
        InlineKeyboardButton(BTN_SUPPORT, callback_data="support"),
        InlineKeyboardButton(BTN_CONTACT, url=CONTACT_URL),
    )
    return kb

def leave_request_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(BTN_LEAVE_REQUEST, url=CONTACT_URL))
    kb.add(InlineKeyboardButton(BTN_BACK, callback_data="menu"))
    return kb

def guides_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for i, (title, _) in enumerate(GUIDES):
        kb.add(InlineKeyboardButton(title, callback_data=f"guide:{i}"))
    kb.add(InlineKeyboardButton(BTN_BACK, callback_data="menu"))
    return kb

# ===================  ВОПРОС ДНЯ  =========================
QUESTION = "Какая мысль чаще всего тормозит тебя?"
OPTIONS = [
    "«Я не успею»",
    "«Не идеально — не делать»",
    "«Что скажут другие?»",
    "«Я потом»",
]

def qod_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for i, opt in enumerate(OPTIONS):
        kb.add(InlineKeyboardButton(opt, callback_data=f"qod_opt:{i}"))
    kb.add(InlineKeyboardButton(BTN_BACK, callback_data="menu"))
    return kb

MINI_TASKS = [
    "Запиши один шаг, который займёт ≤10 минут, и сделай его прямо сегодня.",
    "Зафиксируй 3 выгоды, которые придут после действия. Вернись к ним вечером.",
    "Спроси себя: «Что самое маленькое я могу сделать за 5 минут?» — и сделай это.",
    "Выбери новое убеждение-вопрос: «А если получится? Что будет дальше?»",
]

# ==================  /start и главное меню  =================
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    # Пытаемся прислать привет-фото
    if os.path.exists(WELCOME_PHOTO):
        try:
            await message.answer_photo(
                photo=InputFile(WELCOME_PHOTO),
                caption=START_TEXT,
                reply_markup=main_menu_kb()
            )
            return
        except Exception:
            pass
    # Если нет фото или не отправилось – просто текст
    await message.answer(START_TEXT, reply_markup=main_menu_kb())

# -------------------- навигация в меню ---------------------
@dp.callback_query_handler(lambda c: c.data == "menu")
async def cb_menu(call: types.CallbackQuery):
    await call.message.edit_reply_markup()  # убираем старые кнопки
    await call.message.answer("Главное меню:", reply_markup=main_menu_kb())
    await call.answer()

# ===================  Наставничество  ======================
@dp.callback_query_handler(lambda c: c.data == "mentoring")
async def cb_mentoring(call: types.CallbackQuery):
    await call.message.answer(MENTORING_TEXT, reply_markup=leave_request_kb())
    await call.answer()

# =====================  Консультация  =======================
@dp.callback_query_handler(lambda c: c.data == "consult")
async def cb_consult(call: types.CallbackQuery):
    await call.message.answer(CONSULTATION_TEXT, reply_markup=leave_request_kb())
    await call.answer()

# =========================  Гайды  ==========================
@dp.callback_query_handler(lambda c: c.data == "guides")
async def cb_guides(call: types.CallbackQuery):
    await call.message.answer("Выбери гайд:", reply_markup=guides_menu_kb())
    await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("guide:"))
async def cb_guide_download(call: types.CallbackQuery):
    idx = int(call.data.split(":")[1])
    title, filename = GUIDES[idx]
    if not os.path.exists(filename):
        await call.message.answer(f"Файл <b>{filename}</b> не найден в репозитории.", reply_markup=back_kb())
        await call.answer()
        return
    try:
        await call.message.answer_document(
            document=InputFile(filename),
            caption=f"«{title}»",
            reply_markup=back_kb()
        )
    except Exception as e:
        await call.message.answer(f"Не удалось отправить файл: {e}", reply_markup=back_kb())
    await call.answer()

# =====================  Вопрос дня  =========================
@dp.callback_query_handler(lambda c: c.data == "qod")
async def cb_qod(call: types.CallbackQuery):
    text = f"{QOD_INTRO}\n<b>{QUESTION}</b>\n\nВыбери вариант:"
    await call.message.answer(text, reply_markup=qod_kb())
    await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("qod_opt:"))
async def cb_qod_answer(call: types.CallbackQuery):
    idx = int(call.data.split(":")[1])
    choice = OPTIONS[idx]
    mini = MINI_TASKS[idx % len(MINI_TASKS)]
    await call.message.answer(
        f"Отлично, ты выбрал: <b>{choice}</b>\n\n"
        f"🔥 Мини‑задание: {mini}",
        reply_markup=back_kb()
    )
    await call.answer()

# =====================  Поддержать  =========================
@dp.callback_query_handler(lambda c: c.data == "support")
async def cb_support(call: types.CallbackQuery):
    if os.path.exists(DONATION_QR):
        try:
            await call.message.answer_photo(
                photo=InputFile(DONATION_QR),
                caption=f"{SUPPORT_QR_CAPTION}\n\n{SUPPORT_TEXT}",
                reply_markup=back_kb()
            )
            await call.answer()
            return
        except Exception:
            pass
    await call.message.answer(SUPPORT_TEXT, reply_markup=back_kb())
    await call.answer()

# =====================  Подписка / Связаться  ===============
@dp.message_handler(commands=["contact"])
async def cmd_contact(message: types.Message):
    await message.answer(CONTACT_TEXT, reply_markup=back_kb())

# ===================  Keep‑Alive веб‑сервер  ================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok","service":"telegram_bot"}')

    def log_message(self, format, *args):
        # подавляем дефолтный лог HTTP‑сервера
        return

def run_keepalive():
    port = int(os.environ.get("PORT", "10000"))
    httpd = HTTPServer(("0.0.0.0", port), HealthHandler)
    try:
        httpd.serve_forever()
    except Exception:
        pass

# ========================  START  ===========================
if __name__ == "__main__":
    # отдельный поток «health» для Render, чтобы не ловить port scan timeout
    Thread(target=run_keepalive, daemon=True).start()

    # запуск бота
    executor.start_polling(dp, skip_updates=True)
