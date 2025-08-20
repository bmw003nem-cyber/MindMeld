# utils.py
import os, json, csv
from datetime import date
from typing import List, Tuple, Set

# Берём только то, что реально нужно
from config import (
    INSIGHTS_FILE,         # например: "insights.json"
    STATS_CSV,             # например: "events.csv"
    WELCOME_PHOTO,         # например: "assets/welcome.jpg"
    DONATION_QR,           # например: "assets/donation_qr.png"
    GUIDES,                # список кортежей [(title, filename), ...]
)

# ---------- Инсайты / Вопрос дня ----------

def _default_insights() -> List[str]:
    # Можно расширить в любое время
    return [
        "Что ты делаешь, когда никто не видит?",
        "Какое маленькое действие ты давно откладываешь — и можешь сделать сегодня?",
        "Где ты сейчас выбираешь страх вместо роста?",
        "Что в твоей жизни просит честности именно сейчас?",
        "Как выглядит твоя идеальная утренняя рутина? Что можешь добавить уже завтра?",
        "Какую одну мысль пора отпустить?",
        "Если бы ты доверился себе на 100%, какой был бы следующий шаг?",
        "Где ты говоришь «да», когда хочется сказать «нет»?",
        "Какое простое действие вернёт тебе энергию сегодня?",
        "Что важно тебе — помимо доказательств другим?",
    ]

def load_insights() -> List[str]:
    """Читает список вопросов/инсайтов из INSIGHTS_FILE, при отсутствии создаёт файл по умолчанию."""
    if not os.path.exists(INSIGHTS_FILE):
        insights = _default_insights()
        try:
            with open(INSIGHTS_FILE, "w", encoding="utf-8") as f:
                json.dump(insights, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[insights] cannot create {INSIGHTS_FILE}: {e}")
        return insights

    try:
        with open(INSIGHTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or not data:
            raise ValueError("insights is empty or not a list")
        return [str(x) for x in data]
    except Exception as e:
        print(f"[insights] failed to load {INSIGHTS_FILE}: {e}")
        return _default_insights()

def get_today_insight() -> str:
    """Детерминированно выбирает инсайт по сегодняшней дате."""
    insights = load_insights()
    if not insights:
        insights = _default_insights()
    idx = date.today().toordinal() % len(insights)
    return insights[idx]

# ---------- Проверки статики (без генерации!) ----------

def ensure_images():
    """Проверяет наличие картинок. Если нет — просто предупреждаем в логах."""
    for path in [WELCOME_PHOTO, DONATION_QR]:
        if not path:
            continue
        if not os.path.exists(path):
            # пробуем в assets/
            alt = os.path.join("assets", os.path.basename(path))
            if os.path.exists(alt):
                continue
            print(f"[assets] WARN: image not found: {path}")

def ensure_pdfs():
    """Проверяет наличие PDF в проекте. Ничего не генерируем."""
    for title, filename in GUIDES:
        # пробуем в папке guides/
        p1 = os.path.join("guides", filename)
        p2 = filename  # возможно лежит в корне
        if os.path.exists(p1) or os.path.exists(p2):
            continue
        print(f"[guides] WARN: PDF not found for guide '{title}': expected '{p1}' or '{p2}'")

# ---------- Статистика и рассылка ----------

def _read_user_ids_from_stats() -> Set[int]:
    """Возвращает набор user_id из CSV-логов событий."""
    users = set()
    if not os.path.exists(STATS_CSV):
        return users
    try:
        with open(STATS_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # заголовок
            for row in reader:
                if len(row) >= 2:
                    try:
                        users.add(int(row[1]))
                    except Exception:
                        pass
    except Exception as e:
        print(f"[stats] read error: {e}")
    return users

def get_stats() -> str:
    """Простая статистика для /stats."""
    users = _read_user_ids_from_stats()
    total_events = 0
    if os.path.exists(STATS_CSV):
        try:
            with open(STATS_CSV, "r", encoding="utf-8") as f:
                total_events = max(0, sum(1 for _ in f) - 1)
        except Exception:
            pass
    return f"Пользователей: {len(users)}\nСобытий: {total_events}"

async def broadcast_message(bot, text: str) -> int:
    """Рассылка по всем user_id, встречавшимся в events.csv."""
    users = _read_user_ids_from_stats()
    sent = 0
    for uid in users:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception as e:
            # не падаем из‑за одного пользователя
            print(f"[broadcast] failed to {uid}: {e}")
    return sent

