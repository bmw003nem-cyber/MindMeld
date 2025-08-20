# bot.py — версия с daily 2.0 (вопрос + мини‑задание + ответы кнопками), с прогрессом на диске

import os, json, time, asyncio, csv, base64
from datetime import datetime, date
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile, ReplyKeyboardRemove, ForceReply
from aiogram.utils import executor
from aiogram.dispatcher.filters import Text
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ===================== CONFIG =====================
from config import (
    BOT_TOKEN, ADMIN_ID, CHANNEL_USERNAME,
    WELCOME_PHOTO, DONATION_QR,
    WELCOME_TEXT, MENTORING_TEXT, CONSULT_TEXT, GUIDES_INTRO,
    REVIEWS_TEXT, DONATE_TEXT, CONTACT_TEXT, INSIGHT_HEADER
)

# ===================== PATHS =====================
BASE_DIR = Path(__file__).resolve().parent
ASSETS = BASE_DIR / "assets"
DATA = BASE_DIR / "data"
DATA.mkdir(exist_ok=True)

INSIGHTS_JSON = ASSETS / "insights.json"   # старый список вопросов/инсайтов
DAILY_STATE_JSON = DATA / "daily_state.json"

STATS_CSV = BASE_DIR / "events.csv"

# ===================== BOT CORE =====================
bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

awaiting_application = {}
awaiting_insight_reply = {}

# ===================== HELPERS =====================
def log_event(user_id: int, event: str):
    try:
        with open(STATS_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if f.tell() == 0:
                w.writerow(["ts", "user_id", "event"])
            w.writerow([datetime.now().isoformat(), user_id, event])
    except Exception as e:
        print("log_event error:", e)

async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

def load_json(path: Path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path: Path, obj):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("save_json error:", e)

# ===================== DAILY 2.0 =====================
# Храним прогресс: { "user_id": {"day": int, "streak": int, "last_id": int, "last_ts": epoch } }
STATE = load_json(DAILY_STATE_JSON, {})

DAILY_FLOW = [
    {
        "id": 1,
        "question": "Удалось ли сегодня уделить 5 минут себе (тишина/дыхание/прогулка)?",
        "answers": ["Да", "Частично", "Нет"],
        "task_yes": "Закрепи результат: 3 минуты тишины перед сном, 10 спокойных вдохов-выдохов.",
        "task_mid": "Сделай сейчас 60 секунд паузы: закрой глаза, расслабь плечи, 10 ровных вдохов.",
        "task_no":  "Выдели 2 минуты. Ровно дыши. Затем одно слово о состоянии.",
        "test": "Какое ощущение после мини‑практики?",
        "test_options": ["Больше энергии", "Спокойнее", "Без изменений"]
    },
    {
        "id": 2,
        "question": "Сделал(а) ли ты сегодня один маленький шаг к важной цели?",
        "answers": ["Да", "Немного", "Нет"],
        "task_yes": "Запиши 1 мысль/навык, который помог. Это твой рабочий инструмент.",
        "task_mid": "Сделай микрошаг 3–5 минут: 3 строки текста, 1 звонок, черновик файла.",
        "task_no":  "Определи самый маленький шаг (до 3 минут) и поставь в календарь на сегодня.",
        "test": "Что чувствуешь после шага?",
        "test_options": ["Уверенность", "Облегчение", "Сопротивление"]
    },
    {
        "id": 3,
        "question": "Удалось ли сегодня не залипать в ленте соцсетей?",
        "answers": ["Да", "Старался", "Нет"],
        "task_yes": "Награди себя 5 минутами любимого дела без экрана.",
        "task_mid": "Таймер 15 минут, телефон в другой комнате. Сделай 1 важное дело.",
        "task_no":  "На 10 минут убери телефон из вида и сфокусируйся на одной задаче.",
        "test": "Как результат маленького детокса?",
        "test_options": ["Концентрация ↑", "Спокойнее", "Пока рано говорить"]
    },
    {
        "id": 4,
        "question": "Был ли сегодня момент, когда ты осознанно выбрал спокойствие вместо спора?",
        "answers": ["Да", "Иногда", "Нет"],
        "task_yes": "Отметь 1 внутреннюю опору, которая помогла сохранить спокойствие.",
        "task_mid": "В следующий спор — пауза 10 секунд, затем короткая фраза без обвинений.",
        "task_no":  "Один спор — перепиши мысленно как конструктивный диалог (2–3 фразы).",
        "test": "Что внутри после практики?",
        "test_options": ["Спокойнее", "Прояснение", "Без изменений"]
    },
    {
        "id": 5,
        "question": "Удалось ли сегодня лечь спать вовремя (±30 минут от цели)?",
        "answers": ["Да", "Почти", "Нет"],
        "task_yes": "Микронаграда: 5 минут приятного чтения без экрана.",
        "task_mid": "Сегодня — экран за 40 минут до сна в сторону, вода, тихий свет.",
        "task_no":  "Поставь время «в постели» на 10 минут раньше, чем обычно.",
        "test": "Как самочувствие сейчас?",
        "test_options": ["Бодрее", "Ок", "Хочется спать"]
    },
    {
        "id": 6,
        "question": "Удалось ли сегодня сделать паузу перед «автоматическим» действием (еда/лента/реакция)?",
        "answers": ["Да", "Иногда", "Нет"],
        "task_yes": "Укрепи навык: завтра повтори в другом триггере.",
        "task_mid": "Отметь 1 триггер и заранее придумай короткую альтернативу (вода/дыхание).",
        "task_no":  "Сегодня — одна пауза на 15 секунд перед любым автоматизмом.",
        "test": "Что поменялось?",
        "test_options": ["Сознательность", "Больше контроля", "Ничего"]
    },
    {
        "id": 7,
        "question": "Удалось ли сделать что-то «для будущего себя» (порядок, список, подготовка)?",
        "answers": ["Да", "Немного", "Нет"],
        "task_yes": "Запиши, что сработало, и повтори через день.",
        "task_mid": "Добавь одну вещь для «завтрашнего себя» (в сумке/на столе/в списке).",
        "task_no":  "Прямо сейчас: 2‑минутное действие, которое завтра сэкономит 10 минут.",
        "test": "Как ощущение после заботы о будущем себе?",
        "test_options": ["Уверенность", "Спокойствие", "Пока нейтрально"]
    }
]

def _user(uid: int):
    suid = str(uid)
    if suid not in STATE:
        STATE[suid] = {"day": 0, "streak": 0, "last_id": 0, "last_ts": 0}
    return STATE[suid]

def _save_state():
    save_json(DAILY_STATE_JSON, STATE)

def _by_id(qid: int):
    for d in DAILY_FLOW:
        if d["id"] == qid:
            return d
    return DAILY_FLOW[0]

def kb_daily_answers(qid: int, answers):
    kb = InlineKeyboardMarkup()
    for a in answers:
        kb.add(InlineKeyboardButton(a, callback_data=f"dqa:{qid}:{a}"))
    return kb

def kb_daily_test(qid: int, options):
    kb = InlineKeyboardMarkup()
    for o in options:
        kb.add(InlineKeyboardButton(o, callback_data=f"dqt:{qid}:{o}"))
    return kb

async def daily_send_question(chat, uid: int):
    u = _user(uid)
    next_id = (u["day"] % len(DAILY_FLOW)) + 1
    d = _by_id(next_id)
    u["last_id"] = d["id"]; _save_state()

    text = f"📌 <b>Вопрос дня</b> ({d['id']}/{len(DAILY_FLOW)})\n\n{d['question']}"
    await bot.send_message(chat, text, reply_markup=kb_daily_answers(d["id"], d["answers"]), parse_mode="HTML")

@dp.message_handler(commands=["daily"])
async def cmd_daily(m: types.Message):
    await daily_send_question(m.chat.id, m.from_user.id)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("dqa:"))
async def daily_answer_cb(c: types.CallbackQuery):
    _, qid, answer = c.data.split(":", 2)
    qid = int(qid)
    d = _by_id(qid)

    if answer == d["answers"][0]:
        task = d["task_yes"]
    elif answer == d["answers"][1]:
        task = d["task_mid"]
    else:
        task = d["task_no"]

    await c.message.answer(f"🎯 Мини‑задание\n{task}\n\nКогда сделаешь — отметь состояние:")
    await c.message.answer(d["test"], reply_markup=kb_daily_test(d["id"], d["test_options"]))
    await c.answer()

@dp.callback_query_handler(lambda c: c.data and c.data.startswith("dqt:"))
async def daily_test_cb(c: types.CallbackQuery):
    _, qid, result = c.data.split(":", 2)
    qid = int(qid)
    uid = c.from_user.id
    u = _user(uid)

    if u.get("last_id") == qid:
        u["day"] = (u["day"] % len(DAILY_FLOW)) + 1
        u["streak"] = u.get("streak", 0) + 1
        u["last_ts"] = int(time.time())
        _save_state()
        await c.message.answer(f"✅ Засчитано! Текущая серия: {u['streak']} дней.\nПриходи завтра → /daily")
    else:
        await c.message.answer("Отметь результат по текущему вопросу /daily.")
    await c.answer()

@dp.message_handler(commands=["progress"])
async def progress_cmd(m: types.Message):
    u = _user(m.from_user.id)
    await m.answer(f"📊 Прогресс\nДень: {max(1,u['day'])}/{len(DAILY_FLOW)}\nСерия: {u['streak']} дней")

# ===================== MAIN MENU =====================
def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Наставничество", callback_data="menu_mentoring"),
        InlineKeyboardButton("Консультация",  callback_data="menu_consult"),
        InlineKeyboardButton("Гайды",         callback_data="menu_guides"),
        InlineKeyboardButton("Отзывы",        callback_data="menu_reviews"),
        InlineKeyboardButton("Донат",         callback_data="menu_donate"),
        InlineKeyboardButton("Связаться",     callback_data="menu_contact"),
        InlineKeyboardButton("Вопрос дня+",   callback_data="go_daily")
    )
    return kb

@dp.callback_query_handler(Text(equals="go_daily"))
async def open_daily(c: types.CallbackQuery):
    await daily_send_question(c.message.chat.id, c.from_user.id); await c.answer()

# ===================== EXISTING HANDLERS =====================
# оставляем твои прежние хендлеры меню и логики — они подтягиваются из handlers.py
from handlers import register_handlers
register_handlers(dp, bot, ADMIN_ID, CHANNEL_USERNAME, WELCOME_PHOTO, DONATION_QR,
                  WELCOME_TEXT, MENTORING_TEXT, CONSULT_TEXT, GUIDES_INTRO,
                  REVIEWS_TEXT, DONATE_TEXT, CONTACT_TEXT, INSIGHT_HEADER, ASSETS, log_event, is_subscribed)

# ===================== SCHEDULER =====================
async def send_daily_prompt():
    # мягкое напоминание вечером
    # если у тебя есть список подписчиков, замени на свой набор user_id
    try:
        subs = set()  # заполни при желании
        for uid in subs:
            try:
                await bot.send_message(uid, "Напоминание: загляни в «Вопрос дня» → /daily 🌿")
            except Exception:
                pass
    except Exception as e:
        print("send_daily_prompt error:", e)

def setup_scheduler():
    try:
        for job in scheduler.get_jobs(): scheduler.remove_job(job.id)
    except Exception:
        pass
    scheduler.add_job(send_daily_prompt, CronTrigger(hour=19, minute=0))
    if not scheduler.running:
        scheduler.start()

# ===================== START =====================
@dp.message_handler(commands=["start"])
async def start_cmd(m: types.Message):
    try:
        if WELCOME_PHOTO and Path(WELCOME_PHOTO).exists():
            await bot.send_photo(m.chat.id, InputFile(WELCOME_PHOTO), caption=WELCOME_TEXT, reply_markup=main_menu())
        else:
            await m.answer(WELCOME_TEXT, reply_markup=main_menu())
    except Exception:
        await m.answer(WELCOME_TEXT, reply_markup=main_menu())
    log_event(m.from_user.id, "start")

if __name__ == "__main__":
    setup_scheduler()
    executor.start_polling(dp, skip_updates=True)
