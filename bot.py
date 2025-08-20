# bot.py
# -*- coding: utf-8 -*-

import os
import csv
import time
import json
import threading
import traceback
from datetime import datetime
from collections import defaultdict

# aiogram 2.x
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# scheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# маленький health-check сервер
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- наши модули ---
from config import (
    BOT_TOKEN, CHANNEL_USERNAME, PARSE_MODE, PORT,
    WELCOME_PHOTO, DONATION_QR,
    INSIGHTS_FILE, STATS_CSV, PROGRESS_CSV,
    GUIDES,
    WELCOME_TEXT, MENTORING_TEXT, CONSULT_TEXT, GUIDES_INTRO,
    REVIEWS_TEXT, DONATE_TEXT, CONTACT_TEXT, INSIGHT_HEADER,
    DAILY_HOUR, DAILY_MINUTE, ADMIN_ID
)
from utils import (
    load_insights, get_today_insight, ensure_images, ensure_pdfs,
    broadcast_message, get_stats
)

# ===================== BOT SETUP =====================
bot = Bot(token=BOT_TOKEN, parse_mode=PARSE_MODE)
dp = Dispatcher(bot)

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

# ===================== RUNTIME STATE =====================
user_downloads = defaultdict(set)   # user_id -> set(pdf_idx)
daily_subscribers = set()
insights_data = load_insights()     # не обязателен в этом файле, но инициализируем

# ===================== LOGGING =====================
def log_event(user_id: int, event: str, details: str = ""):
    try:
        is_new = not os.path.exists(STATS_CSV)
        with open(STATS_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["timestamp", "user_id", "event", "details"])
            w.writerow([datetime.now().isoformat(), user_id, event, details])
    except Exception as e:
        print(f"[log] error: {e}", flush=True)

# ===================== KEYBOARDS =====================
def kb_main() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🎯 Наставничество", callback_data="mentoring"),
        InlineKeyboardButton("💬 Консультация", callback_data="consultation"),
    )
    kb.add(
        InlineKeyboardButton("📚 Гайды", callback_data="guides"),
        InlineKeyboardButton("🔮 Вопрос дня", callback_data="insight"),
    )
    kb.add(
        InlineKeyboardButton("💎 Отзывы", callback_data="reviews"),
        InlineKeyboardButton("💛 Поддержать", callback_data="donate"),
    )
    kb.add(InlineKeyboardButton("📞 Связаться", callback_data="contact"))
    return kb

def kb_guides() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for i, (title, _) in enumerate(GUIDES, start=1):
        kb.add(InlineKeyboardButton(f"{i}. {title}", callback_data=f"guide_{i-1}"))
    kb.add(InlineKeyboardButton("← Назад", callback_data="back_main"))
    return kb

def kb_back() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("← Назад", callback_data="back_main"))
    return kb

# ===================== UTILS =====================
async def is_user_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

# ===================== HANDLERS =====================
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    log_event(user_id, "start")
    try:
        if os.path.exists(WELCOME_PHOTO):
            with open(WELCOME_PHOTO, "rb") as photo:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=WELCOME_TEXT,
                    reply_markup=kb_main(),
                )
        else:
            await message.answer(WELCOME_TEXT, reply_markup=kb_main())
    except Exception as e:
        print(f"[start] send error: {e}", flush=True)
        await message.answer(WELCOME_TEXT, reply_markup=kb_main())

@dp.callback_query_handler(lambda c: c.data == "back_main")
async def cb_back_main(cq: types.CallbackQuery):
    try:
        await cq.message.edit_text(WELCOME_TEXT, reply_markup=kb_main())
    except Exception:
        await cq.message.answer(WELCOME_TEXT, reply_markup=kb_main())
    await cq.answer()

@dp.callback_query_handler(lambda c: c.data == "mentoring")
async def cb_mentoring(cq: types.CallbackQuery):
    log_event(cq.from_user.id, "mentoring_view")
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📝 Оставить заявку", url="https://t.me/Mr_Nikto4"))
    kb.add(InlineKeyboardButton("← Назад", callback_data="back_main"))
    try:
        await cq.message.edit_text(MENTORING_TEXT, reply_markup=kb)
    except Exception:
        await cq.message.answer(MENTORING_TEXT, reply_markup=kb)
    await cq.answer()

@dp.callback_query_handler(lambda c: c.data == "consultation")
async def cb_consult(cq: types.CallbackQuery):
    log_event(cq.from_user.id, "consultation_view")
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📝 Оставить заявку", url="https://t.me/Mr_Nikto4"))
    kb.add(InlineKeyboardButton("← Назад", callback_data="back_main"))
    try:
        await cq.message.edit_text(CONSULT_TEXT, reply_markup=kb)
    except Exception:
        await cq.message.answer(CONSULT_TEXT, reply_markup=kb)
    await cq.answer()

@dp.callback_query_handler(lambda c: c.data == "guides")
async def cb_guides(cq: types.CallbackQuery):
    log_event(cq.from_user.id, "guides_view")
    try:
        await cq.message.edit_text(GUIDES_INTRO, reply_markup=kb_guides())
    except Exception:
        await cq.message.answer(GUIDES_INTRO, reply_markup=kb_guides())
    await cq.answer()

async def send_guide_to_user(user_id: int, guide_idx: int, cq: types.CallbackQuery):
    title, filename = GUIDES[guide_idx]
    # ищем либо в /guides, либо в корне
    path = filename
    if not os.path.exists(path):
        alt = os.path.join("guides", filename)
        if os.path.exists(alt):
            path = alt

    if not os.path.exists(path):
        await cq.answer("❌ Файл не найден", show_alert=True)
        return

    try:
        with open(path, "rb") as doc:
            await bot.send_document(user_id, doc, caption=f"📚 {title}\n\nГайд отправлен.")
        user_downloads[user_id].add(guide_idx)
        log_event(user_id, "guide_download", title)
        try:
            await cq.message.edit_text(f"✅ Гайд «{title}» отправлен в личные сообщения.", reply_markup=kb_back())
        except Exception:
            await cq.message.answer(f"✅ Гайд «{title}» отправлен в личные сообщения.", reply_markup=kb_back())
    except Exception as e:
        print(f"[guide] send error: {e}", flush=True)
        await cq.answer("❌ Ошибка отправки", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith("guide_"))
async def cb_guide_pick(cq: types.CallbackQuery):
    uid = cq.from_user.id
    idx = int(cq.data.split("_")[1])

    if user_downloads[uid]:
        await cq.answer("❌ Можно скачать только один гайд", show_alert=True)
        return

    if not await is_user_subscribed(uid):
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        kb.add(InlineKeyboardButton("✅ Я подписался", callback_data=f"checksub_{idx}"))
        kb.add(InlineKeyboardButton("← Назад", callback_data="guides"))
        try:
            await cq.message.edit_text(
                "Чтобы скачать гайд, подпишись на канал и нажми «Я подписался».",
                reply_markup=kb
            )
        except Exception:
            await cq.message.answer(
                "Чтобы скачать гайд, подпишись на канал и нажми «Я подписался».",
                reply_markup=kb
            )
        await cq.answer()
        return

    await send_guide_to_user(uid, idx, cq)
    await cq.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("checksub_"))
async def cb_check_sub(cq: types.CallbackQuery):
    uid = cq.from_user.id
    idx = int(cq.data.split("_")[1])
    if await is_user_subscribed(uid):
        await send_guide_to_user(uid, idx, cq)
    else:
        await cq.answer("❌ Подписка не найдена. Подпишись на канал.", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "reviews")
async def cb_reviews(cq: types.CallbackQuery):
    log_event(cq.from_user.id, "reviews_view")
    try:
        await cq.message.edit_text(REVIEWS_TEXT, reply_markup=kb_back())
    except Exception:
        await cq.message.answer(REVIEWS_TEXT, reply_markup=kb_back())
    await cq.answer()

@dp.callback_query_handler(lambda c: c.data == "donate")
async def cb_donate(cq: types.CallbackQuery):
    log_event(cq.from_user.id, "donate_view")
    try:
        if os.path.exists(DONATION_QR):
            with open(DONATION_QR, "rb") as ph:
                await bot.send_photo(cq.from_user.id, ph, caption=DONATE_TEXT, reply_markup=kb_back())
        else:
            await cq.message.edit_text(DONATE_TEXT, reply_markup=kb_back())
    except Exception:
        await cq.message.answer(DONATE_TEXT, reply_markup=kb_back())
    await cq.answer()

@dp.callback_query_handler(lambda c: c.data == "contact")
async def cb_contact(cq: types.CallbackQuery):
    log_event(cq.from_user.id, "contact_view")
    try:
        await cq.message.edit_text(CONTACT_TEXT, reply_markup=kb_back())
    except Exception:
        await cq.message.answer(CONTACT_TEXT, reply_markup=kb_back())
    await cq.answer()

# ---------- ВОПРОС ДНЯ ----------
@dp.callback_query_handler(lambda c: c.data == "insight")
async def cb_insight(cq: types.CallbackQuery):
    uid = cq.from_user.id
    log_event(uid, "insight_view")
    today = get_today_insight()

    kb = InlineKeyboardMarkup(row_width=1)
    if uid in daily_subscribers:
        kb.add(InlineKeyboardButton("❌ Отписаться от рассылки", callback_data="ins_unsub"))
    else:
        kb.add(InlineKeyboardButton("✅ Подписаться на рассылку", callback_data="ins_sub"))
    kb.add(InlineKeyboardButton("← Назад", callback_data="back_main"))

    text = f"{INSIGHT_HEADER}\n\n{today}"
    try:
        await cq.message.edit_text(text, reply_markup=kb)
    except Exception:
        await cq.message.answer(text, reply_markup=kb)
    await cq.answer()

@dp.callback_query_handler(lambda c: c.data == "ins_sub")
async def cb_ins_sub(cq: types.CallbackQuery):
    uid = cq.from_user.id
    daily_subscribers.add(uid)
    log_event(uid, "daily_subscribe")
    await cq.answer("✅ Подписка оформлена. Каждый день в 08:00 Мск пришлю «Вопрос дня».", show_alert=True)
    # обновим клавиатуру
    try:
        await cq.message.edit_reply_markup(
            InlineKeyboardMarkup(row_width=1)
            .add(InlineKeyboardButton("❌ Отписаться от рассылки", callback_data="ins_unsub"))
            .add(InlineKeyboardButton("← Назад", callback_data="back_main"))
        )
    except Exception:
        pass

@dp.callback_query_handler(lambda c: c.data == "ins_unsub")
async def cb_ins_unsub(cq: types.CallbackQuery):
    uid = cq.from_user.id
    daily_subscribers.discard(uid)
    log_event(uid, "daily_unsubscribe")
    await cq.answer("❌ Рассылка отключена.", show_alert=True)
    try:
        await cq.message.edit_reply_markup(
            InlineKeyboardMarkup(row_width=1)
            .add(InlineKeyboardButton("✅ Подписаться на рассылку", callback_data="ins_sub"))
            .add(InlineKeyboardButton("← Назад", callback_data="back_main"))
        )
    except Exception:
        pass

# ===================== DAILY SENDER =====================
async def send_daily_insight():
    if not daily_subscribers:
        return
    text = f"{INSIGHT_HEADER}\n\n{get_today_insight()}"
    sent = 0
    for uid in list(daily_subscribers):
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception as e:
            print(f"[daily] send failed to {uid}: {e}", flush=True)
            if "bot was blocked" in str(e).lower():
                daily_subscribers.discard(uid)
    print(f"[daily] sent to {sent} users", flush=True)

def setup_scheduler():
    scheduler.add_job(
        send_daily_insight,
        CronTrigger(hour=DAILY_HOUR, minute=DAILY_MINUTE, timezone="Europe/Moscow"),
        id="daily_insight",
        replace_existing=True,
    )
    scheduler.start()
    print("[scheduler] started", flush=True)

# ===================== ADMIN =====================
@dp.message_handler(commands=["stats"])
async def cmd_stats(message: types.Message):
    if ADMIN_ID and message.from_user.id == ADMIN_ID:
        try:
            s = get_stats()
            await message.answer(f"📊 Статистика:\n\n{s}")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")

@dp.message_handler(commands=["broadcast"])
async def cmd_broadcast(message: types.Message):
    if ADMIN_ID and message.from_user.id == ADMIN_ID:
        text = message.get_args()
        if not text:
            await message.answer("Использование: /broadcast <текст>")
            return
        cnt = await broadcast_message(text)
        await message.answer(f"✅ Отправлено: {cnt}")

# ===================== HEALTH CHECK =====================
class HealthHandler(BaseHTTPRequestHandler):
    def _ok(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(b'{"status":"ok","service":"telegram_bot"}')

    def do_GET(self):
        self._ok()

    def do_HEAD(self):
        self._ok()

    def log_message(self, fmt, *args):
        # глушим стандартный спам логов http.server
        return

def run_health_forever():
    while True:
        try:
            server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
            print(f"[health] listening on 0.0.0.0:{PORT}", flush=True)
            server.serve_forever()
        except Exception as e:
            print(f"[health] crashed: {e}\n{traceback.format_exc()}", flush=True)
            time.sleep(3)

# ===================== MAIN =====================
if __name__ == "__main__":
    # создать CSV если не существует
    if not os.path.exists(STATS_CSV):
        with open(STATS_CSV, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["timestamp", "user_id", "event", "details"])

    # фоновые сервисы
    threading.Thread(target=run_health_forever, daemon=True).start()

    # подготовка ассетов (если в utils реализовано)
    ensure_images()
    ensure_pdfs()

    # планировщик
    setup_scheduler()

    # запускаем polling
    # ВАЖНО: ошибка aiogram.utils.exceptions.TerminatedByOtherGetUpdates
    # бывает только если одновременно запущены две копии бота с одним токеном.
    # Убедись, что у тебя ОДИН web‑service на Render и нет параллельного «ручного» запуска.
    print("[bot] start polling", flush=True)
    executor.start_polling(dp, skip_updates=True)
