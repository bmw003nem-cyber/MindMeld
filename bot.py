# -*- coding: utf-8 -*-
# bot.py — основной код бота под config.py
from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import config  # локальный файл config.py

# =========================
# ЛОГИ
# =========================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")

# =========================
# ПОДГОТОВКА ХРАНИЛИЩА
# =========================
Path(config.DATA_DIR).mkdir(parents=True, exist_ok=True)

def db() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    with closing(db()) as conn, conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            subscribed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS answers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question_id TEXT,
            answer_index INTEGER,
            correct INTEGER,
            answered_on TEXT, -- YYYY-MM-DD в TZ
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS guide_clicks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            guide_slug TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

init_db()

# =========================
# УТИЛИТЫ
# =========================
TZ = pytz.timezone(config.TZ)

def today_tz() -> date:
    return datetime.now(TZ).date()

def fmt_bold(text: str) -> str:
    return f"**{text}**"  # жирный для Telegram

def upsert_user(ctx: ContextTypes.DEFAULT_TYPE, u: Update) -> int:
    chat = u.effective_chat
    user = u.effective_user
    with closing(db()) as conn, conn:
        conn.execute(
            """
            INSERT INTO users (chat_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
              username=excluded.username,
              first_name=excluded.first_name,
              last_name=excluded.last_name
            """,
            (chat.id, user.username, user.first_name, user.last_name),
        )
        row = conn.execute("SELECT id FROM users WHERE chat_id=?", (chat.id,)).fetchone()
        return int(row["id"])

def reply_main_menu() -> ReplyKeyboardMarkup:
    titles = config.BUTTONS["main_menu"]
    rows = [
        [KeyboardButton(titles[0]), KeyboardButton(titles[1])],
        [KeyboardButton(titles[2]), KeyboardButton(titles[3])],
        [KeyboardButton(titles[4]), KeyboardButton(titles[5])],
        [KeyboardButton(titles[6])],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def links_row(*keys: str) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    for k in keys:
        meta = config.INLINE_LINKS.get(k)
        if meta:
            row.append(InlineKeyboardButton(text=meta["title"], url=meta["url"]))
    return row

def get_today_question() -> dict:
    day_idx = today_tz().toordinal()
    return config.get_question_for_day(day_idx)

def question_keyboard(q: dict) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for idx, opt in enumerate(q["options"]):
        cb = f"ans|{q['id']}|{idx}|{today_tz().isoformat()}"
        buttons.append([InlineKeyboardButton(text=opt, callback_data=cb)])
    return InlineKeyboardMarkup(buttons)

def can_answer_today(user_id: int, qid: str, day: str) -> bool:
    if config.ALLOW_RETRY_SAME_DAY:
        return True
    with closing(db()) as conn:
        row = conn.execute(
            "SELECT 1 FROM answers WHERE user_id=? AND question_id=? AND answered_on=?",
            (user_id, qid, day),
        ).fetchone()
        return row is None

def save_answer(user_id: int, qid: str, idx: int, correct: bool, day: str) -> None:
    with closing(db()) as conn, conn:
        conn.execute(
            """
            INSERT INTO answers(user_id, question_id, answer_index, correct, answered_on)
            VALUES(?,?,?,?,?)
            """,
            (user_id, qid, idx, 1 if correct else 0, day),
        )

async def send_question(chat_id: int, context: ContextTypes.DEFAULT_TYPE, preface=True) -> None:
    q = get_today_question()
    header = fmt_bold(config.QUESTION_OF_DAY_HEADER)
    intro = config.TEXT_QUESTION_OF_DAY_INTRO
    text = f"{header}\n\n{intro}\n\n{fmt_bold(q['text'])}"
    kb = question_keyboard(q)
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )

# =========================
# ХЕНДЛЕРЫ
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    upsert_user(context, update)
    await update.message.reply_text(
        config.START_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_main_menu(),
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        config.HELP_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_main_menu(),
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    upsert_user(context, update)
    text = (update.message.text or "").strip()

    if text == config.BUTTONS["main_menu"][0]:
        await update.message.reply_text(config.TEXT_QUESTION_OF_DAY_INTRO, parse_mode=ParseMode.MARKDOWN)
        await send_question(update.effective_chat.id, context)

    elif text == config.BUTTONS["main_menu"][1]:
        await show_guides_list(update, context)

    elif text == config.BUTTONS["main_menu"][2]:
        await send_diagnostics(update, context)

    elif text == config.BUTTONS["main_menu"][3]:
        await send_mentoring(update, context)

    elif text == config.BUTTONS["main_menu"][4]:
        await send_reviews(update, context)

    elif text == config.BUTTONS["main_menu"][5]:
        await open_channel(update, context)

    elif text == config.BUTTONS["main_menu"][6]:
        await help_cmd(update, context)

    else:
        await update.message.reply_text("Выбери действие в меню ниже.", reply_markup=reply_main_menu())

async def show_guides_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows: list[list[InlineKeyboardButton]] = []
    for g in config.GUIDES:
        rows.append([InlineKeyboardButton(text=g["title"], callback_data=f"guide|{g['slug']}")])
    rows.append(links_row("reviews", "channel", "mentor"))
    await update.message.reply_text(
        config.TEXT_GUIDES,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(rows),
    )

async def send_diagnostics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = [links_row("mentor"), links_row("reviews"), links_row("channel")]
    await update.message.reply_text(
        config.TEXT_DIAGNOSTICS,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(rows),
    )

async def send_mentoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = [links_row("mentor"), links_row("reviews"), links_row("channel")]
    await update.message.reply_text(
        config.TEXT_MENTORING,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(rows),
    )

async def send_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = [links_row("reviews")]
    await update.message.reply_text(
        fmt_bold("Отзывы и кейсы учеников"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(rows),
    )

async def open_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = [links_row("channel")]
    await update.message.reply_text(
        "Открыть канал с постами и форматами «сериала»:",
        reply_markup=InlineKeyboardMarkup(rows),
    )

# --------- CALLBACKS ----------
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = (query.data or "")
    await query.answer()

    if data.startswith("ans|"):
        _, qid, sidx, day = data.split("|", 3)
        idx = int(sidx)
        user_id = upsert_user(context, update)
        q: Optional[dict] = next((x for x in config.QUESTIONS if x["id"] == qid), None)
        if not q:
            await query.edit_message_text("Вопрос устарел. Попроси новый через меню.")
            return

        if not can_answer_today(user_id, qid, day):
            await query.edit_message_text("Ответ уже засчитан на сегодня. Возвращайся завтра 🙂")
            return

        correct = (idx == int(q["correct"]))
        save_answer(user_id, qid, idx, correct, day)

        prefix = config.TEXT_AFTER_ANSWER_RIGHT if correct else config.TEXT_AFTER_ANSWER_WRONG
        msg = f"{prefix}\n\n{fmt_bold('Разбор:')} {q['explain']}\n\n{config.TEXT_EXPLANATION_FOOTER}"
        kb = InlineKeyboardMarkup([links_row("channel", "reviews", "mentor")])

        try:
            await query.edit_message_text(text=msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        except Exception as e:
            log.warning("edit_message failed: %s", e)
            await query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data.startswith("guide|"):
        _, slug = data.split("|", 1)
        await show_guide_detail(update, context, slug)

async def show_guide_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, slug: str) -> None:
    upsert_user(context, update)
    g = config.safe_get_guide(slug)
    if not g:
        await update.effective_chat.send_message("Гайд не найден. Выбери из списка ещё раз.")
        return

    body = [fmt_bold(g["title"]), g.get("description", "")]
    steps = g.get("steps") or []
    if steps:
        body.append("\n".join(f"• {s}" for s in steps))
    text = "\n\n".join([p for p in body if p])

    await update.effective_chat.send_message(
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([links_row("mentor", "channel")]),
    )

# --------- ПОДПИСКА НА АВТО-ВОПРОС ----------
async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    upsert_user(context, update)
    with closing(db()) as conn, conn:
        conn.execute("UPDATE users SET subscribed=1 WHERE chat_id=?", (update.effective_chat.id,))
    when = f"{config.QUESTION_PUSH_TIME.hour:02d}:{config.QUESTION_PUSH_TIME.minute:02d}"
    await update.message.reply_text(
        f"Готово! Буду присылать «Вопрос дня» каждый день в {when} ({config.TZ}).",
        reply_markup=reply_main_menu(),
    )

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    upsert_user(context, update)
    with closing(db()) as conn, conn:
        conn.execute("UPDATE users SET subscribed=0 WHERE chat_id=?", (update.effective_chat.id,))
    await update.message.reply_text("Ок, отключил ежедневную доставку вопроса.", reply_markup=reply_main_menu())

# =========================
# ПЛАНИРОВЩИК
# =========================
scheduler = None

async def push_daily_question(context: ContextTypes.DEFAULT_TYPE) -> None:
    with closing(db()) as conn:
        rows = conn.execute("SELECT chat_id FROM users WHERE subscribed=1").fetchall()
    for r in rows:
        try:
            await send_question(r["chat_id"], context, preface=False)
        except Exception as e:
            log.warning("Failed to send daily question to %s: %s", r["chat_id"], e)

def setup_scheduler(app: Application) -> None:
    global scheduler
    if scheduler:
        return
    scheduler = AsyncIOScheduler(timezone=TZ)
    hh = config.QUESTION_PUSH_TIME.hour
    mm = config.QUESTION_PUSH_TIME.minute
    trigger = CronTrigger(hour=hh, minute=mm, second=0, timezone=TZ)
    scheduler.add_job(push_daily_question, trigger, args=[app.bot], id="daily_q")
    scheduler.start()
    log.info("Scheduler started for daily question at %02d:%02d %s", hh, mm, config.TZ)

# =========================
# АДМИН-КОМАНДЫ
# =========================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with closing(db()) as conn:
        total = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        subs = conn.execute("SELECT COUNT(*) c FROM users WHERE subscribed=1").fetchone()["c"]
        today = today_tz().isoformat()
        ans = conn.execute("SELECT COUNT(*) c FROM answers WHERE answered_on=?", (today,)).fetchone()["c"]
    msg = [fmt_bold("Статистика"), f"Пользователей: {total}", f"Подписаны на авто‑вопрос: {subs}", f"Ответов сегодня ({today}): {ans}"]
    await update.message.reply_text("\n".join(msg), parse_mode=ParseMode.MARKDOWN)

# =========================
# MAIN
# =========================
def main() -> None:
    token = config.BOT_TOKEN
    if not token:
        raise RuntimeError("Не найден BOT_TOKEN. Задай его как переменную окружения (Render / .env / Docker).")

    app: Application = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("stats", stats))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    app.add_handler(CallbackQueryHandler(callbacks))

    setup_scheduler(app)
    log.info("Bot is up.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()