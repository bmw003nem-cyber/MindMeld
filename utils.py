import os, json, csv
from datetime import date
from typing import List

from aiogram import Bot
from config import BOT_TOKEN, STATS_CSV, INSIGHTS_STORE, WELCOME_PHOTO, DONATION_QR, GUIDES

# -------- Ассеты (проверка наличия, ничего не создаём) --------
def ensure_images():
    for path in (WELCOME_PHOTO, DONATION_QR):
        if not os.path.exists(path):
            alt = f"assets/{os.path.basename(path)}"
            if os.path.exists(alt):
                continue
            print(f"[warn] file not found: {path} (не критично)")

def ensure_pdfs():
    for _, filename in GUIDES:
        if not os.path.exists(filename):
            alt = f"guides/{filename}"
            if os.path.exists(alt):
                continue
            print(f"[warn] guide not found: {filename} (не критично)")

# -------- Инсайты (вопрос дня) --------
def _default_insights() -> List[str]:
    return [
        "Какие твои решения основаны на страхе?",
        "Что ты делаешь, когда никто не видит?",
        "Что из того, что ты откладывал, стоит сделать сегодня?",
        "Где ты делаешь «как надо», а не «как честно»?",
        "Если убрать чувство вины — что решишь иначе?",
        "Что сейчас просит твоего внимания больше всего?",
        "Какое маленькое действие приблизит тебя к большому?",
    ]

def load_insights() -> List[str]:
    if os.path.exists(INSIGHTS_STORE):
        try:
            with open(INSIGHTS_STORE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and all(isinstance(x, str) for x in data):
                    return data
        except Exception as e:
            print(f"[insights] read error: {e}")
    # создаём файл с дефолтными вопросами
    data = _default_insights()
    try:
        with open(INSIGHTS_STORE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[insights] write default error: {e}")
    return data

def get_today_insight() -> str:
    items = load_insights()
    if not items:
        items = _default_insights()
    idx = (date.today().toordinal()) % len(items)
    return items[idx]

# -------- Статистика / рассылка --------
def _collect_user_ids_from_events() -> list[int]:
    users = set()
    if not os.path.exists(STATS_CSV):
        return []
    try:
        with open(STATS_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # заголовок
            for row in reader:
                if len(row) >= 2:
                    try:
                        uid = int(row[1])
                        users.add(uid)
                    except:
                        pass
    except Exception as e:
        print(f"[stats] read error: {e}")
    return sorted(users)

def get_stats() -> str:
    total_users = len(_collect_user_ids_from_events())
    starts = downloads = subs = unsubs = 0
    if os.path.exists(STATS_CSV):
        with open(STATS_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for _, _, event, _ in reader:
                if event == "start": starts += 1
                elif event == "guide_download": downloads += 1
                elif event == "daily_subscribe": subs += 1
                elif event == "daily_unsubscribe": unsubs += 1
    return (
        f"Пользователей (по событиям): {total_users}\n"
        f"Стартов: {starts}\n"
        f"Скачиваний гайдов: {downloads}\n"
        f"Подписок на «Вопрос дня»: {subs}\n"
        f"Отписок: {unsubs}"
    )

async def broadcast_message(text: str) -> int:
    """Простая рассылка по всем user_id, встреченным в events.csv."""
    ids = _collect_user_ids_from_events()
    if not ids:
        return 0
    bot = Bot(token=BOT_TOKEN)
    sent = 0
    for uid in ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception as e:
            print(f"[broadcast] fail to {uid}: {e}")
    await bot.session.close()
    return sent
