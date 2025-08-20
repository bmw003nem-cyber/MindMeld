from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile, ReplyKeyboardRemove, ForceReply
from aiogram.dispatcher.filters import Text
from pathlib import Path

def register_handlers(dp, bot, ADMIN_ID, CHANNEL_USERNAME, WELCOME_PHOTO, DONATION_QR,
                      WELCOME_TEXT, MENTORING_TEXT, CONSULT_TEXT, GUIDES_INTRO,
                      REVIEWS_TEXT, DONATE_TEXT, CONTACT_TEXT, INSIGHT_HEADER,
                      ASSETS, log_event, is_subscribed):

    @dp.callback_query_handler(Text(startswith="menu_mentoring"))
    async def menu_mentoring(c: types.CallbackQuery):
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Оставить заявку", callback_data="apply_mentoring"))
        kb.add(InlineKeyboardButton("В меню", callback_data="go_menu"))
        await c.message.answer(MENTORING_TEXT, reply_markup=kb); await c.answer()
        log_event(c.from_user.id, "open_mentoring")

    @dp.callback_query_handler(Text(startswith="menu_consult"))
    async def menu_consult(c: types.CallbackQuery):
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Оставить заявку", callback_data="apply_consult"))
        kb.add(InlineKeyboardButton("В меню", callback_data="go_menu"))
        await c.message.answer(CONSULT_TEXT, reply_markup=kb); await c.answer()
        log_event(c.from_user.id, "open_consult")

    @dp.callback_query_handler(Text(startswith="menu_guides"))
    async def menu_guides(c: types.CallbackQuery):
        await c.message.answer(GUIDES_INTRO, reply_markup=_guides_menu(ASSETS)); await c.answer()
        log_event(c.from_user.id, "open_guides")

    def _guides_menu(ASSETS):
        kb = InlineKeyboardMarkup(row_width=1)
        # динамически выводим PDF из папки assets
        for p in sorted(ASSETS.glob("*.pdf")):
            kb.add(InlineKeyboardButton(p.stem.replace("_", " "), callback_data=f"guide::{p.name}"))
        kb.add(InlineKeyboardButton("Вопрос дня / Инсайт", callback_data="go_daily"))
        kb.add(InlineKeyboardButton("В меню", callback_data="go_menu"))
        return kb

    @dp.callback_query_handler(Text(startswith="guide::"))
    async def send_guide(c: types.CallbackQuery):
        _, fname = c.data.split("::", 1)
        fpath = ASSETS / fname
        if not await is_subscribed(c.from_user.id):
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(
                InlineKeyboardButton("Подписаться на канал", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"),
                InlineKeyboardButton("Проверить подписку", callback_data=c.data),  # повторная проверка
                InlineKeyboardButton("В меню", callback_data="go_menu")
            )
            await c.message.answer("Чтобы скачать гайд — подпишись на канал и нажми «Проверить подписку».", reply_markup=kb)
            await c.answer(); return

        if fpath.exists():
            await bot.send_document(c.message.chat.id, InputFile(str(fpath)), caption="Гайд готов 🙌")
            log_event(c.from_user.id, f"download_guide:{fname}")
        else:
            await c.message.answer("Файл временно недоступен. Напиши мне в личку, пришлю 🙏")
        await c.answer()

    @dp.callback_query_handler(Text(startswith="menu_reviews"))
    async def menu_reviews(c: types.CallbackQuery):
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("В меню", callback_data="go_menu"))
        await c.message.answer(REVIEWS_TEXT, reply_markup=kb); await c.answer()
        log_event(c.from_user.id, "open_reviews")

    @dp.callback_query_handler(Text(startswith="menu_donate"))
    async def menu_donate(c: types.CallbackQuery):
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("В меню", callback_data="go_menu"))
        try:
            if Path(DONATION_QR).exists():
                await bot.send_photo(c.message.chat.id, InputFile(DONATION_QR), caption=DONATE_TEXT, reply_markup=kb)
            else:
                await c.message.answer(DONATE_TEXT, reply_markup=kb)
        except Exception:
            await c.message.answer(DONATE_TEXT, reply_markup=kb)
        await c.answer(); log_event(c.from_user.id, "open_donate")

    @dp.callback_query_handler(Text(startswith="menu_contact"))
    async def menu_contact(c: types.CallbackQuery):
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("В меню", callback_data="go_menu"))
        await c.message.answer(CONTACT_TEXT, reply_markup=kb); await c.answer()
        log_event(c.from_user.id, "open_contact")

    # заявки
    awaiting_application = {}

    @dp.callback_query_handler(Text(startswith="apply_mentoring"))
    async def apply_mentoring(c: types.CallbackQuery):
        awaiting_application[c.from_user.id] = "Наставничество"
        await c.message.answer("Напиши одним сообщением: твой запрос + контакт (ник/телефон).", reply_markup=ReplyKeyboardRemove())
        await c.answer()

    @dp.callback_query_handler(Text(startswith="apply_consult"))
    async def apply_consult(c: types.CallbackQuery):
        awaiting_application[c.from_user.id] = "Консультация"
        await c.message.answer("Напиши одним сообщением: твой запрос + контакт (ник/телефон).", reply_markup=ReplyKeyboardRemove())
        await c.answer()

    @dp.message_handler(lambda m: m.from_user.id in awaiting_application)
    async def catch_application(m: types.Message):
        section = awaiting_application.pop(m.from_user.id, "Не указано")
        u = m.from_user
        admin_msg = f"📥 Новая заявка\nРаздел: {section}\nОт: @{u.username or 'no_username'} (id {u.id})\n\nТекст:\n{m.text or '(без текста)'}"
        try:
            await bot.send_message(ADMIN_ID, admin_msg)
        except Exception:
            pass
        await m.answer("Принял 🙌 Отвечу в личке в ближайшее время.", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("В меню", callback_data="go_menu")))
        log_event(m.from_user.id, f"send_application:{section}")
