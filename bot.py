# -*- coding: utf-8 -*-
"""
MindMeld Bot — финальная версия (inline-прозрачные кнопки)
- Flask keep-alive (/ и /health) для Render + UptimeRobot
- Приветствие с фото (assets/welcome.jpg)
- «Поддержать» с QR (assets/qr.png)
- «Гайды»: выдаёт один PDF после проверки подписки на @vse_otvety_vnutri_nas
- «Вопрос дня 2.0»: варианты + свободный ответ + ежедневное напоминание 09:00 Europe/Moscow
- «Наставничество», «Консультация», «Диагностика», «Отзывы», «Связаться»
- Запуск: polling (как у тебя), один инстанс на токен
"""

import logging
import os
from threading import Thread
from datetime import datetime, time as dtime
import pytz

from flask import Flask
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ─────────────────────────── ЛОГИ ───────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger("mindmeld_bot")

# ───────────────────────── НАСТРОЙКИ ────────────────────────
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN пуст. Укажи его в Render → Environment.")

# Канал для проверки подписки на гайды
CHANNEL_USERNAME = "@vse_otvety_vnutri_nas"
CHANNEL_ID = ""  # можно указать numeric id канала, если знаешь

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
    "Это не курс и не вебинар. Это твоя личная трансформация, где мы смотрим не на один кусочек, "
    "а на всю жизнь целиком: тело и энергию, мышление и режим, окружение, внутреннюю опору и твоё предназначение.\n\n"
    "📌 <b>Как устроено наставничество:</b>\n"
    "• 4 недели — 14 тем;\n"
    "• задания каждые 2 дня, чтобы прожить и закрепить изменения;\n"
    "• закрытый Telegram-канал со всей информацией;\n"
    "• моя постоянная личная поддержка;\n"
    "• по завершении — доступ в сообщество «Осознанные люди», где мы идём дальше.\n\n"
    "✨ <b>Что ты получишь за 4 недели:</b>\n"
    "• ясность — поймёшь, кто ты и чего хочешь на самом деле;\n"
    "• дело, которое приносит радость и доход;\n"
    "• энергию, которой хватит и на работу, и на жизнь;\n"
    "• уверенность и внутреннюю опору;\n"
    "• инструменты, которые останутся с тобой и будут работать каждый день.\n\n"
    "Главное отличие: книги и курсы дают знания, но откаты возвращают тебя в старое. "
    "Наставничество — это когда ты не один: рядом проводник, и вместе мы доводим до результата.\n\n"
    "👉 <b>Хочешь проверить, насколько это твоё?</b> Жми «Оставить заявку» и приходи на бесплатную диагностику."
)

CONSULTATION_TEXT = (
    "<b>Консультация — 60 минут, которые помогут сдвинуться с места</b>\n\n"
    "Это личная встреча со мной 1-на-1 (онлайн). За час мы разбираем твой запрос и собираем <b>пошаговый план</b>, "
    "с которым можно двигаться дальше. <b>Запись остаётся у тебя.</b>\n\n"
    "📍 <b>Что включено:</b>\n"
    "• Определим твою точку А — где ты сейчас.\n"
    "• Разберём, что мешает двигаться.\n"
    "• Определим точку Б — чего ты хочешь.\n"
    "• Сложим пошаговый план на 14–30 дней.\n\n"
    "🔥 <b>Что получаешь:</b>\n"
    "• ясность, куда идти и зачем,\n"
    "• чёткие шаги и практики под твой запрос,\n"
    "• понимание, как обходить блоки и не застревать снова.\n\n"
    "<b>Формат:</b> онлайн (Google Meet/Zoom). <b>60 минут.</b>\n"
    "После — запись и план остаются у тебя.\n\n"
    "👉 Жми <b>«Оставить заявку»</b>, если хочешь навести порядок в голове и увидеть конкретный путь.\n\n"
    "<i>Сомневаешься, с чего начать?</i> Жми «Записаться на диагностику» — это бесплатно, 30 минут."
)

GUIDES_HEADER = (
    "<b>Выбери один гайд</b>\n"
    "⚠️ Важно: получить можно <b>только один</b> гайд (чтобы не распыляться и дойти до результата).\n\n"
    "Каждый гайд — это <b>практический PDF</b> с упражнениями на 20–40 минут, которые помогают не просто «понять», "
    "а <b>сделать</b>.\n\n"
    "💡 Перед скачиванием бот проверит подписку на канал — доступ открывается только подписчикам."
)

DIAG_TEXT = (
    "<b>Бесплатная диагностика — 30 минут, чтобы понять твой запрос и формат помощи</b>\n\n"
    "Это короткая стратегическая встреча со мной, где мы:\n"
    "• проясняем твой запрос и цель;\n"
    "• смотрим, что мешает сейчас;\n"
    "• решаем, подойдёт ли тебе консультация или наставничество, и чем они помогут;\n"
    "• даю 1–2 шага, с которых можно начать уже сегодня.\n\n"
    "🔎 Цель диагностики — понять, <b>подхожу ли я тебе как проводник</b> и какой формат даст лучший результат.\n\n"
    "👉 <b>Записаться на диагностику:</b> по кнопке ниже."
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

# ───────────────── Состояние (QOD/Гайды) ────────────────────
USER_STATE = {}             # временное состояние QOD
USER_GUIDE_RECEIVED = set() # кто уже получил один гайд

# ───────────────────── ЭКРАНЫ/ПОТОКИ ────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        with open(WELCOME_PHOTO, "rb") as f:
            await ctx.bot.send_photo(chat_id, photo=f, caption=WELCOME_TEXT,
                                     parse_mode=ParseMode.HTML, reply_markup=menu_inline_kb())
    except Exception as e:
        log.warning("WELCOME_PHOTO send failed: %s", e)
        await ctx.bot.send_message(chat_id, WELCOME_TEXT,
                                   parse_mode=ParseMode.HTML, reply_markup=menu_inline_kb())

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
        await q.message.edit_text(MENTORSHIP_TEXT, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Оставить заявку", callback_data="req:mentorship")],
            [InlineKeyboardButton("🧭 Записаться на диагностику", url=DIAGNOSTIC_URL)],
            [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
        ])); return

    if data == "nav:consultation":
        await q.message.edit_text(CONSULTATION_TEXT, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Оставить заявку", callback_data="req:consultation")],
            [InlineKeyboardButton("🧭 Записаться на диагностику", url=DIAGNOSTIC_URL)],
            [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
        ])); return

    if data == "nav:guides":
        await q.message.edit_text(GUIDES_HEADER, parse_mode=ParseMode.HTML, reply_markup=guides_kb()); return

    if data == "nav:qod":
        await send_qod_entry(update, ctx, edit=True); return

    if data == "nav:reviews":
        await q.message.edit_text("Отзывы:", reply_markup=reviews_kb()); return

    if data == "nav:support":
        await send_support(update, ctx, via_callback=True); return

    if data == "nav:contact":
        await q.message.edit_text("Связаться со мной:", reply_markup=contact_kb()); return

    if data == "nav:diagnostics":
        await q.message.edit_text(DIAG_TEXT, parse_mode=ParseMode.HTML, reply_markup=diagnostics_kb()); return

    # заявки
    if data == "req:mentorship":
        await q.message.edit_text("Оставить заявку на наставничество — напиши мне в личку:", reply_markup=contact_kb()); return
    if data == "req:consultation":
        await q.message.edit_text("Оставить заявку на консультацию — напиши мне в личку:", reply_markup=contact_kb()); return

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
        await update.callback_query.message.edit_text(caption, parse_mode=ParseMode.HTML, reply_markup=support_kb())
    else:
        await ctx.bot.send_message(chat_id, caption, parse_mode=ParseMode.HTML, reply_markup=support_kb())

# ─────────── Гайды (1 шт. после проверки подписки) ───────────
async def handle_guide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id

    if uid in USER_GUIDE_RECEIVED:
        await q.message.edit_text(
            "Кажется, ты уже получил свой гайд. Закрой текущий цикл — и приходи за следующим на эфир/в мастер‑разбор.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]])
        )
        return

    key = (q.data or "").split(":", 1)[1]
    filename = GUIDE_FILES.get(key)
    if not filename:
        await q.message.edit_text("Файл не найден.",
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
        await q.message.edit_text("Подпишись на канал, и доступ к гайдам откроется. 👍",
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]]))
        return

    try:
        with open(filename, "rb") as f:
            await q.message.reply_document(InputFile(f, filename=filename),
                                           caption="Держи! Пусть зайдёт в работу сегодня.",
                                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]]))
        USER_GUIDE_RECEIVED.add(uid)
    except FileNotFoundError:
        await q.message.edit_text("PDF пока недоступен на сервере — проверь, что файл лежит рядом с ботом.",
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]]))

# ─────────── ВОПРОС ДНЯ 2.0 ───────────
async def send_qod_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Ответить сейчас", callback_data="qod:start")],
        [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
    ])
    text = ("<b>Вопрос дня</b>\n"
            "Маленький шаг сегодня — большой сдвиг за месяц. "
            "Отвечай честно для себя: это займёт 30–60 секунд. (Доступен и свободный ответ.)")
    if edit:
        await update.callback_query.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
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
        await q.message.edit_text("Как ответишь?\n• выбери вариант;\n• или напиши свой свободный ответ.", reply_markup=kb); return

    if data == "qod:variants":
        USER_STATE[uid] = {"stage": "variants"}
        idx = datetime.now().weekday() % len(QUESTION_INTROS)
        question, options = QUESTION_INTROS[idx]
        USER_STATE[uid]["question"] = question
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(opt, callback_data=f"qod:pick:{opt}")] for opt in options] +
                                  [[InlineKeyboardButton("← Назад", callback_data="nav:menu")]])
        await q.message.edit_text(question, reply_markup=kb); return

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
        await q.message.edit_text(f"Принято ✅\nСохрани для себя: {choice}.\nХочешь добавить пару слов?", reply_markup=kb); return

    if data == "qod:add_comment":
        USER_STATE[uid]["stage"] = "await_comment"
        await q.message.edit_text("Напиши коротко (1–2 предложения). Что важного для тебя на сегодня?",
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]])); return

    if data == "qod:done":
        await q.message.edit_text("Главное — маленький реальный шаг. Увидимся завтра ✌️",
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Поставить напоминание на завтра", callback_data="qod:remind")],
                                                                     [InlineKeyboardButton("← Назад", callback_data="nav:menu")]]))
        USER_STATE.pop(uid, None); return

    if data == "qod:remind":
        tz = pytz.timezone("Europe/Moscow")
        job_name = f"qodremind_{uid}"
        for job in ctx.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()
        ctx.job_queue.run_daily(qod_reminder, dtime(hour=9, minute=0, tzinfo=tz), name=job_name, data=uid)
        await q.message.edit_text("Напомню завтра в 09:00. Можно отключить командой /stopremind.",
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="nav:menu")]])); return

async def qod_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    uid = ctx.job.data
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Ответить сейчас", callback_data="qod:start")]])
    await ctx.bot.send_message(uid, "Вопрос дня ✨", reply_markup=kb)

# ─────────── Обработчик текстов (для QOD-комментария) ───────
async def message_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else None
    st = USER_STATE.get(uid or -1)
    if st and st.get("stage") == "await_comment":
        USER_STATE.pop(uid, None)
        await update.message.reply_text(
            "Спасибо, записал ✅\nВозвращайся завтра — будет новый вопрос.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Поставить напоминание на завтра", callback_data="qod:remind")],
                [InlineKeyboardButton("← Назад", callback_data="nav:menu")]
            ])
        )
    else:
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
    keep_alive()  # HTTP‑сервер для Render

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CommandHandler("stopremind", stopremind))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))

    log.info("Bot started (inline menu + keep‑alive, polling).")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
