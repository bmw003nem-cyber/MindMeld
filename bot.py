# -*- coding: utf-8 -*-
"""
MindMeld — бот с «Вопросом дня 2.0»
- /start — приветствие + меню
- Кнопка «Вопрос дня» — вопрос с вариантами ответа
- После ответа — мини‑задание на день
- Логирование всех ответов в events.csv
- Подписка на ежедневную рассылку вопроса
- Keep-alive веб‑сервер (Render ждёт открытый порт)
- Автоперезапуск polling при сетевых сбоях
"""

import os
import csv
import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, date

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler

# ===================== КОНФИГ =====================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN пуст. Задай его в переменных окружения Render.")

# Папка с ассетами (картинки приветствия/QR и т.д.)
ASSETS_DIR = "assets"
WELCOME_PHOTO = os.path.join(ASSETS_DIR, "welcome.jpg.jpg")  # как у тебя в репо
DONATION_QR = os.path.join(ASSETS_DIR, "donation_qr.png")

# Канал (если есть проверка подписки — можно подключить позже)
CHANNEL_USERNAME = "@vse_otvety_vnutri_nas"

# Файл логов
EVENTS_CSV = "events.csv"

# Хранилище подписчиков рассылки (на примитиве; можно заменить на файл/БД)
daily_subscribers = set()

# ===================== КОНТЕНТ «ВОПРОС ДНЯ 2.0» =====================

# Каждый вопрос: {text, options, tasks}
# options — список вариантов; tasks — словарь {index->текст мини‑задания}
QUESTIONS = [
    {
        "text": "Что сегодня для тебя важнее всего?",
        "options": ["Сделать шаг к цели", "Позаботиться о теле", "Спокойный день", "Общение с близкими"],
        "tasks": {
            0: "Выбери одно действие, которое реально продвинет тебя к цели, и сделай его до вечера.",
            1: "Сделай 20‑минутную прогулку или разминку + 2 стакана воды.",
            2: "Сделай 10‑минутную дыхательную практику перед сном.",
            3: "Напиши одному важному человеку тёплое сообщение/встречу."
        }
    },
    {
        "text": "Какая мысль чаще всего тормозит тебя?",
        "options": ["«Я не успею»", "«Не идеально — не делать»", "«Что скажут другие?»", "«Я потом»"],
        "tasks": {
            0: "Выдели 25 минут на приоритет и отключи уведомления (техника Pomodoro).",
            1: "Сделай мини‑результат за 30 минут. Не идеально — но сделай.",
            2: "Сделай маленькое действие тихо для себя. Никаких отчётов другим.",
            3: "Выбери одно дело и сделай его прямо сейчас в течение 10 минут."
        }
    },
    {
        "text": "Где сейчас больше всего энергии?",
        "options": ["Тело", "Дело/работа", "Отношения", "Тишина/одиночество"],
        "tasks": {
            0: "Сделай 30 приседаний/отжиманий/тягу резинки — что угодно на 10 минут.",
            1: "Определи 1 ключевую задачу и сделай первый шаг (≤15 минут).",
            2: "Назначь встречу/звонок/совместное дело с важным человеком.",
            3: "Выключи всё на 20 минут и побудь в тишине. Без телефона."
        }
    },
    # Добавишь свои вопросы по аналогии…
]


# ===================== УТИЛИТЫ =====================

def ensure_events_csv():
    if not os.path.exists(EVENTS_CSV):
        with open(EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "user_id", "event", "details"])

def log_event(user_id: int, event: str, details: str = ""):
    ensure_events_csv()
    with open(EVENTS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now().isoformat(timespec="seconds"), user_id, event, details])

def day_index() -> int:
    """Стабильный индекс на день (чтобы у всех был один и тот же вопрос)"""
    return (date.today().toordinal()) % len(QUESTIONS)

# ===================== БОТ =====================

bot = Bot(BOT_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)

# ---------- Клавиатуры ----------
def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🧠 Вопрос дня", callback_data="menu:qod"),
        InlineKeyboardButton("🔔 Подписаться на рассылку", callback_data="menu:sub"),
    )
    kb.add(
        InlineKeyboardButton("📩 Отписаться", callback_data="menu:unsub"),
        InlineKeyboardButton("📕 Наставничество", callback_data="menu:mentoring"),
    )
    kb.add(
        InlineKeyboardButton("💬 Отзывы", url="https://t.me/your_reviews_link"),
        InlineKeyboardButton("❤️ Поддержать", callback_data="menu:donate"),
    )
    return kb

def question_keyboard(q_idx: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for i, opt in enumerate(QUESTIONS[q_idx]["options"]):
        kb.add(InlineKeyboardButton(f"• {opt}", callback_data=f"q:{q_idx}:{i}"))
    return kb

# ---------- Приветствие ----------
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    log_event(user_id, "start", "user started bot")
    text = (
        "Привет, рад видеть тебя в пространстве!\n\n"
        "Здесь — инструменты для ясности, энергии и действий без выгорания.\n"
        "Начни с <b>Вопроса дня</b> — один клик, и у тебя есть фокус + мини‑задание на сегодня."
    )
    if os.path.exists(WELCOME_PHOTO):
        try:
            with open(WELCOME_PHOTO, "rb") as p:
                await message.answer_photo(p, caption=text, reply_markup=main_menu())
        except Exception:
            await message.answer(text, reply_markup=main_menu())
    else:
        await message.answer(text, reply_markup=main_menu())

# ---------- Меню ----------
@dp.callback_query_handler(lambda c: c.data.startswith("menu:"))
async def on_menu(call: types.CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    action = call.data.split(":", 1)[1]

    if action == "qod":
        await send_question(call.message.chat.id)
        return

    if action == "sub":
        daily_subscribers.add(user_id)
        log_event(user_id, "subscribe_daily")
        await call.message.answer("🔔 Подписка на ежедневную рассылку включена. "
                                  "Каждое утро ты будешь получать «Вопрос дня».")
        return

    if action == "unsub":
        daily_subscribers.discard(user_id)
        log_event(user_id, "unsubscribe_daily")
        await call.message.answer("🔕 Отписал от рассылки «Вопрос дня».")
        return

    if action == "mentoring":
        await call.message.answer(MENTORING_TEXT, reply_markup=mentoring_menu())
        return

    if action == "donate":
        if os.path.exists(DONATION_QR):
            with open(DONATION_QR, "rb") as q:
                await call.message.answer_photo(q, caption=DONATE_TEXT)
        else:
            await call.message.answer(DONATE_TEXT)
        return

# ---------- Отправка вопроса ----------
async def send_question(chat_id: int):
    idx = day_index()
    q = QUESTIONS[idx]
    text = f"🧠 <b>Вопрос дня</b>\n\n{q['text']}\n\nВыбери вариант:"
    await bot.send_message(chat_id, text, reply_markup=question_keyboard(idx))

# ---------- Обработка ответа ----------
@dp.callback_query_handler(lambda c: c.data.startswith("q:"))
async def on_answer(call: types.CallbackQuery):
    await call.answer()
    user_id = call.from_user.id
    _, s_idx, s_opt = call.data.split(":")
    idx = int(s_idx)
    opt = int(s_opt)
    q = QUESTIONS[idx]
    choice = q["options"][opt]
    task = q["tasks"].get(opt, "Сделай один малый шаг, который приблизит тебя к важному.")

    # лог
    log_event(user_id, "qod_answer", json.dumps({"q_idx": idx, "option": opt, "choice": choice}, ensure_ascii=False))

    # подтверждение + мини‑задание
    await call.message.answer(
        f"✅ <b>Записал!</b> Ты выбрал: «{choice}».\n\n"
        f"🔥 <b>Мини‑задание на сегодня:</b>\n{task}\n\n"
        "Можешь вернуться к меню или подождать следующего вопроса завтра.",
        reply_markup=main_menu()
    )

# ---------- Наставничество ----------
MENTORING_TEXT = (
    "<b>Наставничество — твой путь к себе и жизни на 100%</b>\n\n"
    "Это не курс и не вебинар. Это твоя личная трансформация, где мы смотрим не на один кусочек, "
    "а на всю жизнь целиком: тело и энергию, мышление и режим, окружение, внутреннюю опору и твоё предназначение.\n\n"
    "📌 <b>Как устроено наставничество:</b>\n"
    "• 4 недели — 14 тем;\n"
    "• задания каждые 2 дня, чтобы прожить и закрепить изменения;\n"
    "• закрытый Telegram-канал со всей информацией;\n"
    "• моя постоянная личная поддержка;\n"
    "• по завершении — доступ в сообщество «Осознанные люди», где мы идём дальше.\n\n"
    "✨ <b>Что ты получишь за 4 недели:</b>\n"
    "→ ясность — поймёшь, кто ты и чего хочешь на самом деле;\n"
    "→ дело, которое приносит радость и доход;\n"
    "→ энергию, которой хватит и на работу, и на жизнь;\n"
    "→ уверенность и внутреннюю опору;\n"
    "→ инструменты, которые останутся с тобой и будут работать каждый день.\n\n"
    "Главное отличие: книги и курсы дают знания, но откаты возвращают в старое. Наставничество — это когда ты не один: "
    "рядом проводник, и вместе мы доводим до результата.\n\n"
    "👉 Хочешь проверить, насколько это твоё? Жми «Оставить заявку» и приходи на бесплатную диагностику."
)

def mentoring_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📝 Оставить заявку", url="https://t.me/your_contact"))
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu"))
    return kb

@dp.callback_query_handler(lambda c: c.data == "back_to_menu")
async def back_to_menu(call: types.CallbackQuery):
    await call.answer()
    await call.message.answer("Главное меню:", reply_markup=main_menu())

# ---------- Донаты ----------
DONATE_TEXT = (
    "Если хочешь поддержать проект:\n"
    "• Tribute — https://t.me/tribute/app?startapp=dq3\n"
    "• СБП по QR — картинка ниже."
)

# ---------- Ежедневная рассылка ----------
async def broadcast_daily_question():
    """Отправка вопроса дня подписчикам."""
    if not daily_subscribers:
        return
    idx = day_index()
    q = QUESTIONS[idx]
    text = f"🧠 <b>Вопрос дня</b>\n\n{q['text']}\n\nВыбери вариант:"
    for uid in list(daily_subscribers):
        try:
            await bot.send_message(uid, text, reply_markup=question_keyboard(idx))
        except Exception as e:
            # если блокировка — удаляем из рассылки
            if "blocked" in str(e).lower():
                daily_subscribers.discard(uid)
            log_event(uid, "daily_send_error", str(e))

# Планировщик
scheduler = BackgroundScheduler(timezone="Europe/Moscow")
# каждый день в 08:00 по Москве
scheduler.add_job(lambda: executor._get_loop(dp).create_task(broadcast_daily_question()),
                  "cron", hour=8, minute=0, id="daily_qod", replace_existing=True)

# ===================== KEEP-ALIVE WEB =====================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "telegram_bot"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args, **kwargs):
        # тихий лог
        return

def run_keepalive_forever():
    while True:
        try:
            port = int(os.environ.get("PORT", "10000"))
            print(f"[keepalive] starting on 0.0.0.0:{port}", flush=True)
            server = HTTPServer(("0.0.0.0", port), HealthHandler)
            server.serve_forever()
        except Exception as e:
            print(f"[keepalive] error: {e}", flush=True)
            time.sleep(3)

# ===================== СТАРТ =====================

def _safe_polling():
    """Защита от внезапных обрывов polling."""
    while True:
        try:
            print("[bot] start_polling...", flush=True)
            executor.start_polling(dp, skip_updates=True)
        except Exception as e:
            print(f"[bot] polling crashed: {e}", flush=True)
            time.sleep(3)

if __name__ == "__main__":
    ensure_events_csv()

    # Keep-alive server в отдельном потоке, чтобы Render видел порт
    threading.Thread(target=run_keepalive_forever, daemon=True).start()

    # Планировщик
    scheduler.start()
    print("[scheduler] started", flush=True)

    # Стартуем polling с авто‑рестартом
    _safe_polling()
