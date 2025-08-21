# -*- coding: utf-8 -*-
"""
MindMeld Bot — финальная сборка
- inline-меню (прозрачные кнопки) + «← Назад»
- Flask keep-alive (/ и /health) для Render + UptimeRobot
- Приветствие с фото (assets/welcome.jpg)
- «Поддержать» с QR (assets/qr.png)
- «Гайды»: 1 PDF после проверки подписки на @vse_otvety_vnutri_nas
- «Вопрос дня 2.0»: варианты + свободный ответ + напоминание 09:00 Europe/Moscow
- «Наставничество», «Консультация», «Диагностика», «Отзывы», «Связаться»
- polling (не нужен webhook)
"""

import logging
import os
from threading import Thread
from datetime import datetime, time as dtime
import pytz

from flask import Flask
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile, ReplyKeyboardRemove
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ─────────────────────────── ЛОГИ ───────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("mindmeld_bot")

# ───────────────────────── НАСТРОЙКИ ────────────────────────
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN пуст. Укажи его в Render → Environment.")

CHANNEL_USERNAME = "@vse_otvety_vnutri_nas"  # для проверки подписки
CHANNEL_ID = ""  # можно numeric id (если знаешь), иначе пусто — используем username

# Ссылки
REVIEWS_CHANNEL_URL = "https://t.me/+4Ov29pR6uj9iYjgy"
REVIEWS_POST_URL    = "https://t.me/vse_otvety_vnutri_nas/287"
TRIBUTE_URL         = "https://t.me/tribute/app?startapp=dq3J"
CONTACT_TG_URL      = "https://t.me/Mr_Nikto4"
DIAGNOSTIC_URL      = "https://t.me/m/0JIRBvZ_NmQy"

# Файлы
WELCOME_PHOTO = "assets/welcome.jpg"
QR_PHOTO      = "assets/qr.png"
GUIDE_FILES = {
    "path_to_self":      "guide_path_to_self.pdf",
    "know_but_dont_do":  "guide_know_but_dont_do.pdf",
    "self_acceptance":   "guide_self_acceptance.pdf",
    "shut_the_mind":     "guide_shut_the_mind.pdf",
}

# ─────────────────────────── ТЕКСТЫ ─────────────────────────
WELCOME_TEXT = (
    "<b>👋 Привет, рад видеть тебя в моём пространстве!</b>\n\n"
    "Я — Роман, предприниматель и наставник. Уже более 200 дней подряд практикую осознанные привычки и исследую, "
    "как маленькие шаги меняют жизнь в долгую. За 8 лет я прошёл путь от «живу по инерции» до состояния, когда сам "
    "создаю свою реальность и знаю, чего хочу.\n\n"
    "В этом пространстве я делюсь тем, что работает:\n"
    "🔧 инструменты для энергии и ясности,\n"
    "🎯 способы находить своё дело и развивать его,\n"
    "🧠 опыт, который помогает не просто «читать и знать», а реально применять.\n\n"
    "<u>Что можно сделать прямо сейчас в этом боте:</u>\n"
    "• Записаться на диагностику или консультацию\n"
    "• Скачать полезные гайды (после подписки на канал)\n"
    "• Узнать о программе наставничества\n"
    "• Перейти в «Вопрос дня»\n\n"
    "🔑 Всё, что тебе нужно, уже внутри тебя. Моя задача — помочь это услышать и сделать твоей опорой."
)

MENTORSHIP_TEXT = (
    "<b>Наставничество — твой путь к себе и жизни на 100%</b>\n\n"
    "📌 <b>Как устроено:</b>\n"
    "• 4 недели — 14 тем;\n"
    "• задания каждые 2 дня;\n"
    "• закрытый Telegram‑канал;\n"
    "• моя личная поддержка;\n"
    "• доступ в сообщество «Осознанные люди».\n\n"
    "✨ <b>За 4 недели ты получишь:</b>\n"
    "• ясность, энергию, внутреннюю опору;\n"
    "• дело, которое приносит радость и доход;\n"
    "• инструменты на каждый день.\n\n"
    "👉 Хочешь проверить, насколько это твоё? Жми «Оставить заявку» или запишись на бесплатную диагностику."
)

CONSULTATION_TEXT = (
    "<b>Консультация — 60 минут, которые помогут сдвинуться с места</b>\n\n"
    "За час разбираем твой запрос и собираем <b>пошаговый план</b> на 14–30 дней. <b>Запись остаётся у тебя.</b>\n\n"
    "📍 <b>Что включено:</b>\n"
    "• Точка А, что мешает, точка Б;\n"
    "• конкретные шаги и практики;\n"
    "• как обходить блоки и не застревать.\n\n"
    "👉 Если сомневаешься, начни с бесплатной диагностики (30 мин)."
)

GUIDES_HEADER = (
    "<b>Выбери один гайд</b>\n"
    "⚠️ Можно получить <b>только один</b>, чтобы сфокусироваться и дойти до результата.\n\n"
    "Перед скачиванием бот проверит подписку на канал."
)

DIAG_TEXT = (
    "<b>Бесплатная диагностика — 30 минут</b>\n\n"
    "Проясним запрос и цель, решим, подойдёт ли консультация или наставничество, дам 1–2 шага на старт.\n\n"
    "Цель — понять, подхожу ли я тебе как проводник и какой формат даст лучший результат."
)

QUESTION_INTROS = [
    ("Сколько времени сегодня ты уделишь себе (чистому присутствию)?", ["2 мин","5 мин","10 мин","20+ мин"]),
    ("Что сегодня даст тебе больше энергии?", ["Сон","Движение","Тишина/медитация","Вода/питание"]),
    ("Где сегодня нужен один честный шаг?", ["Здоровье","Дело","Отношения","Дом/быт"]),
    ("Что ты готов отпустить сегодня?", ["Сомнения","Спешку","Контроль","Оправдания"]),
    ("Какой минимум сделаешь при любой погоде?", ["1 действие","3 действия","5 действий","Сначала 1 — потом ещё"]),
]

# ────────────────────── KEEP‑ALIVE HTTP ─────────────────────
http = Flask(__name__)

@http.get("/")
def home():
    return "Bot is running", 200

@http.get("/health")
def health():
    return "ok", 200

def _run_http():
    port = int(os.getenv("PORT", "10000"))
    http.run(host="0.0.0.0", port=port)

def keep_alive():
    Thread(target=_run_http, daemon=True).start()

# ──────────────────── КНОПКИ (INLINE) ───────────────────────
def menu_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Наставничество", callback_data="nav:mentorship"),
         InlineKeyboardButton("💬 Консультация", callback_data="nav:consultation")],
        [InlineKeyboardButton("🧭 Диагностика (30 мин, бесплатно)", callback_data="nav:diagnostics")],
        [InlineKeyboardButton("📚 Гайды", callback_data="nav:guides"),
         InlineKeyboardButton("🔮 Вопрос дня", callback_data="nav:qod")],
        [InlineKeyboardButton("💎 Отзывы", callback_data="nav:reviews"),
         InlineKeyboardButton("💛 Поддержать", callback_data="nav:support")],
        [InlineKeyboardButton("📞 Связаться", callback_data="nav:contact")]
    ])

def reviews_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Открыть канал с отзывами", url=REVIEWS_CHANNEL_URL)],
        [InlineKeyboardButton("Пост‑подборка", url=REVIEWS_POST_URL)],
        [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
    ])

def support_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Открыть Tribute", url=TRIBUTE_URL)],
        [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
    ])

def contact_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Написать в Telegram", url=CONTACT_TG_URL)],
        [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
    ])

def diagnostics_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Записаться на диагностику", url=DIAGNOSTIC_URL)],
        [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
    ])

def guides_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Путь к себе", callback_data="guide:path_to_self")],
        [InlineKeyboardButton("Знаю, но не делаю", callback_data="guide:know_but_dont_do")],
        [InlineKeyboardButton("Принятие себя", callback_data="guide:self_acceptance")],
        [InlineKeyboardButton("Заткнуть мозг", callback_data="guide:shut_the_mind")],
        [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
    ])

# ───────────── Служебные хранилища ─────────────
USER_STATE = {}             # для Вопроса дня
USER_GUIDE_RECEIVED = set() # кто уже получил один гайд

LEGACY_BUTTON_TEXTS = {
    "Наставничество","Консультация","Гайды","Вопрос дня",
    "Отзывы","Поддержать","Диагностика (30 мин, бесплатно)","Связаться"
}

# ───────────── Универсальная правка сообщений ─────────────
async def safe_edit(q, text, reply_markup=None, parse_mode=ParseMode.HTML):
    """
    Правим сообщение безопасно:
    - если исходное было фото с caption — правим caption;
    - если текст — правим text;
    - иначе отправляем новое.
    """
    try:
        msg = q.message
        if getattr(msg, "photo", None):
            return await msg.edit_caption(caption=text, parse_mode=parse_mode, reply_markup=reply_markup)
        if msg.text:
            return await msg.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        return await msg.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception:
        return await q.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)

# ───────────────────── ЭКРАНЫ/ПОТОКИ ────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Жёстко снимаем возможную старую reply‑клавиатуру
    try:
        await ctx.bot.send_message(chat_id, " ", reply_markup=ReplyKeyboardRemove())
    except Exception:
        pass

    # Приветствие с фото + inline‑меню
    try:
        with open(WELCOME_PHOTO, "rb") as f:
            await ctx.bot.send_photo(
                chat_id,
                photo=f,
                caption=WELCOME_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=menu_inline_kb(),
            )
    except Exception as e:
        log.warning("WELCOME_PHOTO send failed: %s", e)
        await ctx.bot.send_message(
            chat_id, WELCOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=menu_inline_kb()
        )

async def hidekeyboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Клавиатура скрыта.", reply_markup=ReplyKeyboardRemove())

async def callbacks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""

    if data == "nav:menu":
        try:
            await q.message.delete()
        except Exception:
            pass
        await ctx.bot.send_message(q.message.chat_id, "Выбирай раздел 👇", reply_markup=menu_inline_kb())
        return

    if data == "nav:mentorship":
        await safe_edit(q, MENTORSHIP_TEXT, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Оставить заявку", callback_data="req:mentorship")],
            [InlineKeyboardButton("🧭 Записаться на диагностику", url=DIAGNOSTIC_URL)],
            [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
        ])); return

    if data == "nav:consultation":
        await safe_edit(q, CONSULTATION_TEXT, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Оставить заявку", callback_data="req:consultation")],
            [InlineKeyboardButton("🧭 Записаться на диагностику", url=DIAGNOSTIC_URL)],
            [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
        ])); return

    if data == "nav:guides":
        await safe_edit(q, GUIDES_HEADER, reply_markup=guides_kb()); return

    if data == "nav:qod":
        await send_qod_entry(update, ctx, edit=True); return

    if data == "nav:reviews":
        await safe_edit(q, "Отзывы:", reply_markup=reviews_kb()); return

    if data == "nav:support":
        await send_support(update, ctx, via_callback=True); return

    if data == "nav:contact":
        await safe_edit(q, "Связаться со мной:", reply_markup=contact_kb()); return

    if data == "nav:diagnostics":
        await safe_edit(q, DIAG_TEXT, reply_markup=diagnostics_kb()); return

    # заявки
    if data == "req:mentorship":
        await safe_edit(q, "Оставить заявку на наставничество — напиши мне в личку:", reply_markup=contact_kb()); return
    if data == "req:consultation":
        await safe_edit(q, "Оставить заявку на консультацию — напиши мне в личку:", reply_markup=contact_kb()); return

    # guides
    if data.startswith("guide:"):
        await handle_guide(update, ctx); return

    # QOD
    if data.startswith("qod:"):
        await qod_callbacks(update, ctx); return

# ─────────── Поддержать / QR ───────────
async def send_support(update: Update, ctx: ContextTypes.DEFAULT_TYPE, via_callback: bool = False):
    chat_id = update.effective_chat.id if update.effective_chat else update.callback_query.message.chat_id
    caption = (
        "<b>Бодоненков Роман Валерьевич</b>\n"
        "Номер договора 5388079294\n\n"
        "<b>💛 Поддержать проект</b>\n"
        "Деньги — это энергия. Если то, что я делаю, ценно для тебя, и хочешь сделать обмен энергией — "
        "можешь отправить донат в любой сумме.\n\n"
        "<b>Способы:</b>\n"
        "• Tribute — открой по кнопке ниже\n"
        "• СБП по QR — картинка ниже.\n\n"
        "Благодарю за вклад — он помогает делать больше ценного контента 🙌"
    )
    try:
        with open(QR_PHOTO, "rb") as f:
            await ctx.bot.send_photo(chat_id, photo=f, caption=caption,
                                     parse_mode=ParseMode.HTML, reply_markup=support_kb())
        if via_callback:
            try:
                await update.callback_query.message.delete()
            except Exception:
                pass
        return
    except Exception as e:
        log.warning("QR send failed: %s", e)

    # запасной вариант — без фото
    if via_callback:
        await safe_edit(update.callback_query, caption, reply_markup=support_kb())
    else:
        await ctx.bot.send_message(chat_id, caption, parse_mode=ParseMode.HTML, reply_markup=support_kb())

# ─────────── Гайды (1 шт. после проверки подписки) ───────────
async def handle_guide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id

    if uid in USER_GUIDE_RECEIVED:
        await safe_edit(q,
            "Кажется, ты уже получил свой гайд. Закрой текущий цикл — и приходи за следующим.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]]))
        return

    key = (q.data or "").split(":", 1)[1]
    filename = GUIDE_FILES.get(key)
    if not filename:
        await safe_edit(q, "Файл не найден.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]]))
        return

    # проверка подписки
    allow = True
    try:
        channel = CHANNEL_ID or CHANNEL_USERNAME
        member = await ctx.bot.get_chat_member(chat_id=channel, user_id=uid)
        status = getattr(member, "status", "left")
        allow = status in ("member", "administrator", "creator")
    except Exception as e:
        log.warning("Channel check failed: %s", e)

    if not allow:
        await safe_edit(q, "Подпишись на канал, и доступ к гайдам откроется 👍",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]]))
        return

    try:
        with open(filename, "rb") as f:
            await q.message.reply_document(
                InputFile(f, filename=filename),
                caption="Держи! Пусть зайдёт в работу сегодня.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]])
            )
        USER_GUIDE_RECEIVED.add(uid)
    except FileNotFoundError:
        await safe_edit(q, "PDF пока недоступен на сервере — проверь, что файл лежит рядом с ботом.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]]))

# ─────────── ВОПРОС ДНЯ 2.0 ───────────
async def send_qod_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Ответить сейчас", callback_data="qod:start")],
        [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
    ])
    text = ("<b>Вопрос дня</b>\n"
            "Маленький шаг сегодня — большой сдвиг за месяц. "
            "Отвечай честно для себя: займёт 30–60 секунд. (Есть и свободный ответ.)")
    if edit:
        await safe_edit(update.callback_query, text, reply_markup=kb)
    else:
        await ctx.bot.send_message(update.effective_chat.id, text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def qod_callbacks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""
    uid = q.from_user.id

    if data == "qod:start":
        USER_STATE[uid] = {"stage": "choose_mode"}
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Выбрать из вариантов", callback_data="qod:variants")],
            [InlineKeyboardButton("Свободный ответ", callback_data="qod:free")],
            [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
        ])
        await safe_edit(q, "Как ответишь?\n• выбери вариант;\n• или напиши свой свободный ответ.", reply_markup=kb); return

    if data == "qod:variants":
        USER_STATE[uid] = {"stage": "variants"}
        idx = datetime.now().weekday() % len(QUESTION_INTROS)
        question, options = QUESTION_INTROS[idx]
        USER_STATE[uid]["question"] = question
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(opt, callback_data=f"qod:pick:{opt}")] for opt in options] +
                                  [[InlineKeyboardButton("← Назад", callback_data="nav:menu")]])
        await safe_edit(q, question, reply_markup=kb); return

    if data.startswith("qod:pick:"):
        choice = data.split(":", 2)[2]
        st = USER_STATE.get(uid, {})
        st["choice"] = choice
        st["stage"] = "after_pick"
        USER_STATE[uid] = st
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Добавить свободный комментарий", callback_data="qod:add_comment")],
            [InlineKeyboardButton("Готово", callback_data="qod:done")],
            [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
        ])
        await safe_edit(q, f"Принято ✅\nСохрани для себя: {choice}.\nХочешь добавить пару слов?", reply_markup=kb); return

    if data == "qod:add_comment":
        USER_STATE[uid]["stage"] = "await_comment"
        await safe_edit(q, "Напиши коротко (1–2 предложения). Что важного для тебя на сегодня?",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]])); return

    if data == "qod:done":
        await safe_edit(q, "Главное — маленький реальный шаг. Увидимся завтра ✌️",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Поставить напоминание на завтра", callback_data="qod:remind")],
                            [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
                        ]))
        USER_STATE.pop(uid, None); return

    if data == "qod:remind":
        tz = pytz.timezone("Europe/Moscow")
        job_name = f"qodremind_{uid}"
        for job in ctx.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()
        ctx.job_queue.run_daily(qod_reminder, dtime(hour=9, minute=0, tzinfo=tz), name=job_name, data=uid)
        await safe_edit(q, "Напомню завтра в 09:00. Можно отключить командой /stopremind.",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]])); return

async def qod_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    uid = ctx.job.data
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Ответить сейчас", callback_data="qod:start")]])
    await ctx.bot.send_message(uid, "Вопрос дня ✨", reply_markup=kb)

# ─────────── Обработчик текстов (QOD комментарий + меню) ────
async def message_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    uid = update.effective_user.id if update.effective_user else None
    st = USER_STATE.get(uid or -1)
    text = (update.message.text or "").strip() if update.message else ""

    # Снять любую старую reply‑клавиатуру
    try:
        await ctx.bot.send_message(chat_id, " ", reply_markup=ReplyKeyboardRemove())
    except Exception:
        pass

    if st and st.get("stage") == "await_comment":
        USER_STATE.pop(uid, None)
        await update.message.reply_text(
            "Спасибо, записал ✅\nВозвращайся завтра — будет новый вопрос.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Поставить напоминание на завтра", callback_data="qod:remind")],
                [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
            ])
        )
        return

    if text in LEGACY_BUTTON_TEXTS:
        await update.message.reply_text("Выбирай раздел 👇", reply_markup=menu_inline_kb())
        return

    await update.message.reply_text("Выбирай раздел 👇", reply_markup=menu_inline_kb())

# ─────────── Отключение напоминаний ───────────
async def stopremind(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    job_name = f"qodremind_{uid}"
    for job in ctx.job_queue.get_jobs_by_name(job_name):
        job.schedule_removal()
    await update.message.reply_text("Напоминания отключены (если были).")

# ─────────────────────────── MAIN ────────────────────────────
def main():
    keep_alive()  # HTTP для Render

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("hide", hidekeyboard))
    app.add_handler(CommandHandler("hidekeyboard", hidekeyboard))
    app.add_handler(CommandHandler("stopremind", stopremind))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))

    log.info("Bot started (inline menu + keep‑alive, polling).")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
