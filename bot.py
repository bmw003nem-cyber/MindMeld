import logging
import os
from datetime import time as dtime, datetime
import pytz
from threading import Thread

from flask import Flask
from telegram import (
    Update, InputFile, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ================== SETTINGS ==================
# Token ONLY from environment (Render → Environment → BOT_TOKEN)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# Channel for subscription check
CHANNEL_USERNAME = "@vse_otvety_vnutri_nas"
CHANNEL_ID = ""  # можно оставить пустым

# Fixed links (as provided)
REVIEWS_CHANNEL_URL = "https://t.me/+4Ov29pR6uj9iYjgy"
REVIEWS_POST_URL    = "https://t.me/vse_otvety_vnutri_nas/287"
TRIBUTE_URL         = "https://t.me/tribute/app?startapp=dq3J"
CONTACT_TG_URL      = "https://t.me/Mr_Nikto4"
DIAGNOSTIC_URL      = "https://t.me/m/0JIRBvZ_NmQy"

# File paths
WELCOME_PHOTO_PATH = "assets/welcome.jpg"
QR_PHOTO_PATH      = "assets/qr.png"
GUIDE_FILES = {
    "path_to_self": "guide_path_to_self.pdf",
    "know_but_dont_do": "guide_know_but_dont_do.pdf",
    "self_acceptance": "guide_self_acceptance.pdf",
    "shut_the_mind": "guide_shut_the_mind.pdf",
}

# ================== TEXTS ==================
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
    ("Сколько времени сегодня ты уделишь себе (чистому присутствию)?",
     ["2 мин", "5 мин", "10 мин", "20+ мин"]),
    ("Что сегодня даст тебе больше энергии?",
     ["Сон", "Движение", "Тишина/медитация", "Вода/питание"]),
    ("Где сегодня нужен один честный шаг?",
     ["Здоровье", "Дело", "Отношения", "Дом/быт"]),
    ("Что ты готов отпустить сегодня?",
     ["Сомнения", "Спешку", "Контроль", "Оправдания"]),
    ("Какой минимум сделаешь при любой погоде?",
     ["1 действие", "3 действия", "5 действий", "Сначала 1 — потом ещё"]),
]

# ============== Keep-alive HTTP (for Render Web Service + UptimeRobot) ==============
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/health")
def health():
    return "ok"

def run_http():
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_http, daemon=True)
    t.start()

# ============== Keyboards ==============
def main_menu_kb():
    rows = [
        [KeyboardButton("🎯 Наставничество"), KeyboardButton("💬 Консультация"), KeyboardButton("📚 Гайды")],
        [KeyboardButton("🔮 Вопрос дня"), KeyboardButton("💎 Отзывы"), KeyboardButton("💛 Поддержать")],
        [KeyboardButton("🧭 Диагностика (30 мин, бесплатно)")],
        [KeyboardButton("📞 Связаться")],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def back_inline_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("← Назад", callback_data="back_to_menu")]])

def mentorship_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Оставить заявку", callback_data="leave_request_mentorship"),
    ], [
        InlineKeyboardButton("🧭 Записаться на диагностику", url=DIAGNOSTIC_URL)
    ], [
        InlineKeyboardButton("← Назад", callback_data="back_to_menu")
    ]])

def consultation_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Оставить заявку", callback_data="leave_request_consultation"),
    ], [
        InlineKeyboardButton("🧭 Записаться на диагностику", url=DIAGNOSTIC_URL)
    ], [
        InlineKeyboardButton("← Назад", callback_data="back_to_menu")
    ]])

def guides_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Путь к себе", callback_data="guide:path_to_self")],
        [InlineKeyboardButton("Знаю, но не делаю", callback_data="guide:know_but_dont_do")],
        [InlineKeyboardButton("Принятие себя", callback_data="guide:self_acceptance")],
        [InlineKeyboardButton("Заткнуть мозг", callback_data="guide:shut_the_mind")],
        [InlineKeyboardButton("← Назад", callback_data="back_to_menu")],
    ])

def reviews_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Открыть канал с отзывами", url=REVIEWS_CHANNEL_URL)],
        [InlineKeyboardButton("Пост‑подборка", url=REVIEWS_POST_URL)],
        [InlineKeyboardButton("← Назад", callback_data="back_to_menu")],
    ])

def support_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Открыть Tribute", url=TRIBUTE_URL)],
        [InlineKeyboardButton("← Назад", callback_data="back_to_menu")],
    ])

def diagnostics_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Записаться на диагностику", url=DIAGNOSTIC_URL)],
        [InlineKeyboardButton("← Назад", callback_data="back_to_menu")],
    ])

# ============== State ==============
USER_STATE = {}
USER_GUIDE_RECEIVED = set()

# ============== Handlers ==============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        with open(WELCOME_PHOTO_PATH, "rb") as f:
            await context.bot.send_photo(chat_id, photo=f, caption=WELCOME_TEXT,
                                         parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())
    except Exception:
        await context.bot.send_message(chat_id, WELCOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("Главное меню:", reply_markup=main_menu_kb())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if text == "🎯 Наставничество":
        await update.message.reply_text(MENTORSHIP_TEXT, parse_mode=ParseMode.HTML, reply_markup=mentorship_kb()); return
    if text == "💬 Консультация":
        await update.message.reply_text(CONSULTATION_TEXT, parse_mode=ParseMode.HTML, reply_markup=consultation_kb()); return
    if text == "📚 Гайды":
        await update.message.reply_text(GUIDES_HEADER, parse_mode=ParseMode.HTML, reply_markup=guides_kb()); return
    if text == "🔮 Вопрос дня":
        await send_qod_entry(update, context); return
    if text == "💎 Отзывы":
        await update.message.reply_text("Отзывы:", reply_markup=reviews_kb()); return
    if text == "💛 Поддержать":
        await send_support(update, context); return
    if text == "📞 Связаться":
        await update.message.reply_text("Связаться со мной:", reply_markup=
            InlineKeyboardMarkup([[InlineKeyboardButton("Написать в Telegram", url=CONTACT_TG_URL)],
                                  [InlineKeyboardButton("← Назад", callback_data="back_to_menu")]])); return
    if text == "🧭 Диагностика (30 мин, бесплатно)":
        await update.message.reply_text(DIAG_TEXT, parse_mode=ParseMode.HTML, reply_markup=diagnostics_kb()); return
    await update.message.reply_text("Выбирай пункт в меню ниже 👇", reply_markup=main_menu_kb())

async def send_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    caption = (f"<b>Бодоненков Роман Валерьевич</b>\n"
               "Номер договора 5388079294\n\n"
               "<b>💛 Поддержать проект</b>\n"
               "Деньги — это энергия. Если то, что я делаю, ценно для тебя, и хочешь сделать обмен энергией — "
               "можешь отправить донат в любой сумме.\n\n"
               "<b>Способы:</b>\n"
               f"• Tribute — открой по кнопке ниже\n"
               "• СБП по QR — картинка ниже.\n\n"
               "Благодарю за вклад — он помогает делать больше ценного контента 🙌")
    try:
        with open(QR_PHOTO_PATH, "rb") as f:
            await context.bot.send_photo(chat_id, photo=f, caption=caption, parse_mode=ParseMode.HTML,
                                         reply_markup=support_kb()); return
    except Exception:
        pass
    await context.bot.send_message(chat_id, caption, parse_mode=ParseMode.HTML, reply_markup=support_kb())

# === Guides ===
async def on_guide_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "back_to_menu":
        await query.message.reply_text("Главное меню:", reply_markup=main_menu_kb()); return

    if data.startswith("guide:"):
        if query.from_user.id in USER_GUIDE_RECEIVED:
            await query.message.reply_text(
                "Кажется, ты уже получил свой гайд. Закрой текущий цикл — и приходи за следующим на эфир/в мастер‑разбор.",
                reply_markup=back_inline_kb()); return

        key = data.split(":")[1]
        filename = GUIDE_FILES.get(key)
        if not filename:
            await query.message.reply_text("Файл не найден.", reply_markup=back_inline_kb()); return

        # subscription check
        allow = True
        try:
            channel = CHANNEL_ID or CHANNEL_USERNAME
            member = await context.bot.get_chat_member(chat_id=channel, user_id=query.from_user.id)
            status = getattr(member, "status", "left")
            allow = status in ("member", "administrator", "creator")
        except Exception as e:
            logging.warning("Channel check failed: %s", e)

        if not allow:
            await query.message.reply_text("Подпишись на канал, и доступ к гайдам откроется. 👍",
                                           reply_markup=back_inline_kb()); return

        try:
            with open(filename, "rb") as f:
                await query.message.reply_document(InputFile(f, filename=filename),
                                                   caption="Держи! Пусть зайдёт в работу сегодня.",
                                                   reply_markup=back_inline_kb())
            USER_GUIDE_RECEIVED.add(query.from_user.id)
        except FileNotFoundError:
            await query.message.reply_text("PDF пока недоступен на сервере — проверь, что файл лежит рядом с ботом.",
                                           reply_markup=back_inline_kb())
        return

# === Question of the Day 2.0 ===
async def send_qod_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id if update.message else update.callback_query.message.chat_id
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Ответить сейчас", callback_data="qod:start")],
        [InlineKeyboardButton("← Назад", callback_data="back_to_menu")]
    ])
    await context.bot.send_message(chat_id, "<b>Вопрос дня</b>\nМаленький шаг сегодня — большой сдвиг за месяц. "
                                            "Отвечай честно для себя: это займёт 30–60 секунд. "
                                            "(Доступен и свободный ответ.)",
                                   parse_mode=ParseMode.HTML, reply_markup=kb)

async def qod_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    await q.answer()
    uid = q.from_user.id

    if data == "back_to_menu":
        await q.message.reply_text("Главное меню:", reply_markup=main_menu_kb()); return

    if data == "qod:start":
        USER_STATE[uid] = {"stage": "choose_mode"}
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Выбрать из вариантов", callback_data="qod:variants")],
            [InlineKeyboardButton("Свободный ответ", callback_data="qod:free")],
            [InlineKeyboardButton("← Назад", callback_data="back_to_menu")]
        ])
        await q.message.reply_text("Как ответишь?\n• выбери вариант;\n• или напиши свой свободный ответ.", reply_markup=kb); return

    if data == "qod:variants":
        USER_STATE[uid] = {"stage": "variants"}
        idx = datetime.now().weekday() % len(QUESTION_INTROS)
        question, options = QUESTION_INTROS[idx]
        USER_STATE[uid]["question"] = question
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(opt, callback_data=f"qod:pick:{opt}")] for opt in options] +
                                  [[InlineKeyboardButton("← Назад", callback_data="back_to_menu")]])
        await q.message.reply_text(question, reply_markup=kb); return

    if data.startswith("qod:pick:"):
        choice = data.split(":", 2)[2]
        st = USER_STATE.get(uid, {})
        st["choice"] = choice
        st["stage"] = "after_pick"
        USER_STATE[uid] = st
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Добавить свободный комментарий", callback_data="qod:add_comment")],
            [InlineKeyboardButton("Готово", callback_data="qod:done")],
            [InlineKeyboardButton("← Назад", callback_data="back_to_menu")]
        ])
        await q.message.reply_text(f"Принято ✅\nСохрани для себя: {choice}.\nХочешь добавить пару слов?",
                                   reply_markup=kb); return

    if data == "qod:add_comment":
        USER_STATE[uid]["stage"] = "await_comment"
        await q.message.reply_text("Напиши коротко (1–2 предложения). Что важного для тебя на сегодня?"); return

    if data == "qod:done":
        await q.message.reply_text("Главное — маленький реальный шаг. Увидимся завтра ✌️",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("Поставить напоминание на завтра", callback_data="qod:remind")
                                   ], [
                                       InlineKeyboardButton("← Назад", callback_data="back_to_menu")
                                   ]]))
        USER_STATE.pop(uid, None); return

    if data == "qod:remind":
        tz = pytz.timezone("Europe/Moscow")
        job_name = f"qodremind_{uid}"
        for job in context.job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()
        context.job_queue.run_daily(qod_reminder, dtime(hour=9, minute=0, tzinfo=tz), name=job_name, data=uid)
        await q.message.reply_text("Напомню завтра в 09:00. Можно отключить командой /stopremind.",
                                   reply_markup=back_inline_kb()); return

async def qod_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    uid = ctx.job.data
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Ответить сейчас", callback_data="qod:start")]])
    await ctx.bot.send_message(uid, "Вопрос дня ✨", reply_markup=kb)

async def stop_remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = f"qodremind_{uid}"
    for job in context.job_queue.get_jobs_by_name(name):
        job.schedule_removal()
    await update.message.reply_text("Напоминания отключены.", reply_markup=main_menu_kb())

# === Free text for QOD comment OR normal routing ===
async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    st = USER_STATE.get(uid)
    if st and st.get("stage") == "await_comment":
        txt = (update.message.text or "").strip()
        USER_STATE.pop(uid, None)
        await update.message.reply_text("Спасибо, записал ✅\nВозвращайся завтра — будет новый вопрос.",
                                        reply_markup=InlineKeyboardMarkup([[
                                            InlineKeyboardButton("Поставить напоминание на завтра", callback_data="qod:remind")
                                        ], [InlineKeyboardButton("← Назад", callback_data="back_to_menu")]]))
        return
    else:
        await handle_text(update, context)

# === Callbacks common ===
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    if data.startswith("guide:") or data == "back_to_menu":
        await on_guide_choice(update, context); return
    if data.startswith("qod:"):
        await qod_callbacks(update, context); return
    if data == "leave_request_mentorship":
        await q.message.reply_text("Оставить заявку на наставничество — напиши мне в личку: ",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("Написать Роману", url=CONTACT_TG_URL)
                                   ], [InlineKeyboardButton("← Назад", callback_data="back_to_menu")]])); return
    if data == "leave_request_consultation":
        await q.message.reply_text("Оставить заявку на консультацию — напиши мне в личку: ",
                                   reply_markup=InlineKeyboardMarkup([[
                                       InlineKeyboardButton("Написать Роману", url=CONTACT_TG_URL)
                                   ], [InlineKeyboardButton("← Назад", callback_data="back_to_menu")]])); return

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN env var is empty. Set it in Render → Environment.")
    # Start tiny HTTP server for Render/UptimeRobot
    keep_alive()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("stopremind", stop_remind))

    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))

    logging.info("Bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
