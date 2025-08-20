import os, json, csv, asyncio, base64, threading, time, traceback
from datetime import datetime
from collections import defaultdict

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import *            # здесь лежат BOT_TOKEN, CHANNEL_USERNAME, GUIDES, тексты и т.п.
from handlers import *          # если у тебя там есть свои вспомогательные обработчики
from utils import *             # load_insights, get_today_insight, ensure_images, ensure_pdfs, get_stats, broadcast_message и т.п.

# ===================== BOT SETUP =====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ===================== SCHEDULER =====================
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

# ===================== DATA =====================
user_downloads = defaultdict(set)        # user_id -> set of downloaded guides
insights_data = load_insights()          # из utils
daily_subscribers = set()                # локально в памяти процесса

# ===================== LOG =====================
def log_event(user_id: int, event: str, details: str = ""):
    try:
        with open(STATS_CSV, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([datetime.now().isoformat(), user_id, event, details])
    except Exception as e:
        print(f"[log] error: {e}")

# ===================== KEYBOARDS =====================
def main_menu():
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

def guides_menu():
    kb = InlineKeyboardMarkup()
    for i, (title, _) in enumerate(GUIDES):
        kb.add(InlineKeyboardButton(f"{i+1}. {title}", callback_data=f"guide_{i}"))
    kb.add(InlineKeyboardButton("← Назад", callback_data="back_main"))
    return kb

def back_main_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("← Назад", callback_data="back_main"))
    return kb

# ===================== SUBSCRIPTION CHECK =====================
async def is_user_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

# ===================== HANDLERS =====================
@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    log_event(user_id, "start")
    try:
        if os.path.exists(WELCOME_PHOTO):
            with open(WELCOME_PHOTO, "rb") as photo:
                await bot.send_photo(user_id, photo, caption=WELCOME_TEXT, reply_markup=main_menu())
        else:
            await message.answer(WELCOME_TEXT, reply_markup=main_menu())
    except Exception as e:
        print(f"[start] {e}")
        await message.answer(WELCOME_TEXT, reply_markup=main_menu())

@dp.callback_query_handler(lambda c: c.data == "back_main")
async def back_to_main(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text(WELCOME_TEXT, reply_markup=main_menu())
    except Exception:
        await callback.message.answer(WELCOME_TEXT, reply_markup=main_menu())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "mentoring")
async def mentoring_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    log_event(user_id, "mentoring_view")

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📝 Оставить заявку", url="https://t.me/Mr_Nikto4"))
    kb.add(InlineKeyboardButton("← Назад", callback_data="back_main"))

    # Текст берём из config.MENTORING_TEXT (ты его обновишь сам)
    try:
        await callback.message.edit_text(MENTORING_TEXT, reply_markup=kb)
    except Exception:
        await callback.message.answer(MENTORING_TEXT, reply_markup=kb)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "consultation")
async def consultation_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    log_event(user_id, "consultation_view")

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📝 Оставить заявку", url="https://t.me/Mr_Nikto4"))
    kb.add(InlineKeyboardButton("← Назад", callback_data="back_main"))
    try:
        await callback.message.edit_text(CONSULT_TEXT, reply_markup=kb)
    except Exception:
        await callback.message.answer(CONSULT_TEXT, reply_markup=kb)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "guides")
async def guides_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    log_event(user_id, "guides_view")
    try:
        await callback.message.edit_text(GUIDES_INTRO, reply_markup=guides_menu())
    except Exception:
        await callback.message.answer(GUIDES_INTRO, reply_markup=guides_menu())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("guide_"))
async def guide_download(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    guide_idx = int(callback.data.split("_")[1])

    # одна бесплатная загрузка
    if user_downloads[user_id]:
        await callback.answer("❌ Можно скачать только один гайд", show_alert=True)
        return

    # подписка на канал
    if not await is_user_subscribed(user_id):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📢 Подписаться", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        kb.add(InlineKeyboardButton("✅ Я подписался", callback_data=f"check_sub_{guide_idx}"))
        kb.add(InlineKeyboardButton("← Назад", callback_data="guides"))
        await callback.message.edit_text(
            "Для скачивания гайда подпишись на канал и нажми «Я подписался»",
            reply_markup=kb,
        )
        await callback.answer()
        return

    await send_guide(callback, guide_idx)

@dp.callback_query_handler(lambda c: c.data.startswith("check_sub_"))
async def check_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    guide_idx = int(callback.data.split("_")[2])

    if await is_user_subscribed(user_id):
        await send_guide(callback, guide_idx)
    else:
        await callback.answer("❌ Подписка не найдена. Подпишись на канал!", show_alert=True)

async def send_guide(callback: types.CallbackQuery, guide_idx: int):
    user_id = callback.from_user.id
    title, filename = GUIDES[guide_idx]
    try:
        file_path = f"guides/{filename}"
        if not os.path.exists(file_path):
            file_path = filename
        if os.path.exists(file_path):
            with open(file_path, "rb") as doc:
                await bot.send_document(user_id, doc, caption=f"📚 {title}\n\nТвой гайд готов! Применяй и делись результатами.")
            user_downloads[user_id].add(guide_idx)
            log_event(user_id, "guide_download", title)
            await callback.message.edit_text(f"✅ Гайд «{title}» отправлен тебе в личные сообщения!", reply_markup=back_main_kb())
        else:
            await callback.answer("❌ Файл не найден", show_alert=True)
    except Exception as e:
        print(f"[guide] {e}")
        await callback.answer("❌ Ошибка отправки файла", show_alert=True)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "reviews")
async def reviews_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    log_event(user_id, "reviews_view")
    try:
        await callback.message.edit_text(REVIEWS_TEXT, reply_markup=back_main_kb())
    except Exception:
        await callback.message.answer(REVIEWS_TEXT, reply_markup=back_main_kb())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "donate")
async def donate_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    log_event(user_id, "donate_view")
    try:
        qr_path = f"assets/{DONATION_QR}"
        if not os.path.exists(qr_path):
            qr_path = DONATION_QR
        if os.path.exists(qr_path):
            with open(qr_path, "rb") as photo:
                await bot.send_photo(user_id, photo, caption=DONATE_TEXT, reply_markup=back_main_kb())
        else:
            await callback.message.edit_text(DONATE_TEXT, reply_markup=back_main_kb())
    except Exception as e:
        print(f"[donate] {e}")
        await callback.message.edit_text(DONATE_TEXT, reply_markup=back_main_kb())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "contact")
async def contact_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    log_event(user_id, "contact_view")
    try:
        await callback.message.edit_text("Связаться: @Mr_Nikto4", reply_markup=back_main_kb())
    except Exception:
        await callback.message.answer("Связаться: @Mr_Nikto4", reply_markup=back_main_kb())
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "insight")
async def insight_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    log_event(user_id, "insight_view")

    today = get_today_insight()
    kb = InlineKeyboardMarkup()
    if user_id in daily_subscribers:
        kb.add(InlineKeyboardButton("❌ Отписаться от рассылки", callback_data="unsubscribe_daily"))
    else:
        kb.add(InlineKeyboardButton("✅ Подписаться на рассылку", callback_data="subscribe_daily"))
    kb.add(InlineKeyboardButton("← Назад", callback_data="back_main"))

    text = f"{INSIGHT_HEADER}\n\n{today}"
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "subscribe_daily")
async def subscribe_daily(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    daily_subscribers.add(user_id)
    log_event(user_id, "daily_subscribe")
    await callback.answer("✅ Подписка оформлена! Каждый день в 8:00 ты получишь вопрос для размышления.", show_alert=True)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ Отписаться от рассылки", callback_data="unsubscribe_daily"))
    kb.add(InlineKeyboardButton("← Назад", callback_data="back_main"))
    await callback.message.edit_reply_markup(reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "unsubscribe_daily")
async def unsubscribe_daily(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    daily_subscribers.discard(user_id)
    log_event(user_id, "daily_unsubscribe")
    await callback.answer("❌ Отписка оформлена", show_alert=True)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Подписаться на рассылку", callback_data="subscribe_daily"))
    kb.add(InlineKeyboardButton("← Назад", callback_data="back_main"))
    await callback.message.edit_reply_markup(reply_markup=kb)

# ===================== ADMIN =====================
@dp.message_handler(commands=["stats"])
async def stats_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        stats = get_stats()
        await message.answer(f"📊 Статистика бота:\n\n{stats}")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")

@dp.message_handler(commands=["broadcast"])
async def broadcast_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.get_args()
    if not text:
        await message.answer("Использование: /broadcast <сообщение>")
        return
    count = await broadcast_message(text)
    await message.answer(f"✅ Отправлено {count} пользователям")

# ===================== KEEP-ALIVE WEB SERVER =====================
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def _respond(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(b'{"status":"ok","service":"telegram_bot"}')
    def do_GET(self):  self._respond()
    def do_HEAD(self): self._respond()
    def log_message(self, format, *args): pass

def _run_keepalive_forever():
    while True:
        try:
            port = int(os.environ.get("PORT", 5000))
            print(f"[keepalive] 0.0.0.0:{port}", flush=True)
            HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
        except Exception as e:
            print(f"[keepalive] crashed: {e}\n{traceback.format_exc()}", flush=True)
            time.sleep(3)

# ===================== DAILY INSIGHTS =====================
async def send_daily_insight():
    if not daily_subscribers:
        return
    insight = get_today_insight()
    text = f"🪄 Вопрос дня\n\n{insight}"
    sent = 0
    for user_id in daily_subscribers.copy():
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception as e:
            print(f"[daily] fail {user_id}: {e}")
            if "bot was blocked" in str(e).lower():
                daily_subscribers.discard(user_id)
    print(f"[daily] sent: {sent}")

# ---- удаляем webhook при старте (чтобы точно работал long polling)
async def on_startup(dp):
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("[startup] webhook removed")
    except Exception as e:
        print(f"[startup] delete_webhook error: {e}")

# ---- планировщик
def setup_scheduler():
    scheduler.add_job(
        send_daily_insight,
        CronTrigger(hour=8, minute=0, timezone="Europe/Moscow"),
        id="daily_insight",
        replace_existing=True,
    )
    scheduler.start()
    print("[scheduler] started")

# ---- keep-alive http (без изменений)
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def _respond(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(b'{"status":"ok","service":"telegram_bot"}')
    def do_GET(self):  self._respond()
    def do_HEAD(self): self._respond()
    def log_message(self, format, *args): pass

def _run_keepalive_forever():
    while True:
        try:
            port = int(os.environ.get("PORT", 5000))
            print(f"[keepalive] 0.0.0.0:{port}", flush=True)
            HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
        except Exception as e:
            print(f"[keepalive] crashed: {e}\n{traceback.format_exc()}", flush=True)
            time.sleep(3)

# ===================== SINGLE ENTRY =====================
if __name__ == "__main__":
    # первый запуск — создаём events.csv
    if not os.path.exists("events.csv"):
        with open("events.csv", "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["timestamp", "user_id", "event", "details"])

    # поднимем keep-alive в отдельном потоке
    threading.Thread(target=_run_keepalive_forever, daemon=True).start()

    ensure_images()
    ensure_pdfs()
    setup_scheduler()

    print("[bot] start_polling (single instance)")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
