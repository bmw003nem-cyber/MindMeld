import logging
import os
import pytz
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from flask import Flask

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Flask для Render ping
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive", 200

@app.route('/health')
def health():
    return "OK", 200

# Главное меню (inline кнопки)
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🎯 Наставничество", callback_data="mentorship"),
         InlineKeyboardButton("💬 Консультация", callback_data="consultation")],
        [InlineKeyboardButton("🧭 Диагностика (30 мин, бесплатно)", callback_data="diagnostics")],
        [InlineKeyboardButton("📚 Гайды", callback_data="guides"),
         InlineKeyboardButton("🧘 Вопрос дня", callback_data="question")],
        [InlineKeyboardButton("💎 Отзывы", callback_data="reviews"),
         InlineKeyboardButton("💛 Поддержать", callback_data="support")],
        [InlineKeyboardButton("📞 Связаться", callback_data="contact")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        chat_id = update.message.chat_id
        if os.path.exists("assets/welcome.jpg"):
            with open("assets/welcome.jpg", "rb") as f:
                await context.bot.send_photo(chat_id, f, caption="Привет! 👋 Добро пожаловать. Выбери пункт меню:", reply_markup=main_menu())
        else:
            await update.message.reply_text("Привет! 👋 Добро пожаловать. Выбери пункт меню:", reply_markup=main_menu())

# Обработка нажатий кнопок
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "mentorship":
        text = "📍 Наставничество — за 4 недели мы распакуем твой потенциал, уберём блоки и ты возьмёшь жизнь в свои руки."
    elif query.data == "consultation":
        text = "💬 Консультация — разбор твоей ситуации и шаги для движения вперёд."
    elif query.data == "diagnostics":
        text = "🧭 Диагностика (30 мин, бесплатно) — выясняем твой запрос и понимаем, смогу ли я помочь. Записаться: https://t.me/m/0JIRBvZ_NmQy"
    elif query.data == "guides":
        text = "📚 Выбери один гайд. ⚠️ Важно: можно получить только один гайд."
    elif query.data == "question":
        text = "🧘 Вопрос дня 2.0: Что сегодня поможет тебе быть в ресурсе?"
    elif query.data == "reviews":
        text = "💎 Отзывы: https://t.me/+4Ov29pR6uj9iYjgy"
    elif query.data == "support":
        if os.path.exists("assets/qr.png"):
            with open("assets/qr.png", "rb") as f:
                await context.bot.send_photo(query.message.chat_id, f, caption="🙏 Поддержать можно по QR-коду.")
            return
        text = "🙏 Поддержать можно по QR-коду."
    elif query.data == "contact":
        text = "📞 Связаться: https://t.me/Mr_Nikto4"
    else:
        text = "Выбери пункт меню:"

    await query.edit_message_text(text=text, reply_markup=main_menu())

# Echo для свободных ответов (например, вопрос дня)
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Спасибо за ответ! 🙏", reply_markup=main_menu())

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Flask запускаем в отдельном потоке
    import threading
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000), daemon=True).start()

    application.run_polling()

if __name__ == "__main__":
    main()
