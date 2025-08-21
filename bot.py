import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from flask import Flask
import os

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Flask(__name__)

@app.route('/health')
def health():
    return "OK", 200

# Главное меню (прозрачные кнопки)
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎯 Наставничество", callback_data="mentorship"),
         InlineKeyboardButton("💬 Консультация", callback_data="consultation"),
         InlineKeyboardButton("📚 Гайды", callback_data="guides")],
        [InlineKeyboardButton("🧘 Вопрос дня", callback_data="question"),
         InlineKeyboardButton("💎 Отзывы", callback_data="reviews"),
         InlineKeyboardButton("💛 Поддержать", callback_data="support")],
        [InlineKeyboardButton("🧭 Диагностика (30 мин, бесплатно)", callback_data="diagnostics"),
         InlineKeyboardButton("📞 Связаться", callback_data="contact")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Выбери пункт меню:", reply_markup=main_menu_keyboard())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=f"Вы выбрали: {query.data}", reply_markup=main_menu_keyboard())

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))

    # Flask + Telegram бот вместе
    import threading
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000), daemon=True).start()

    application.run_polling()

if __name__ == "__main__":
    main()
