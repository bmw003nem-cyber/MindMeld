# Question Bot — релиз под ID 252641015

Готово к деплою на Render / локальный запуск / Docker. Твой admin ID уже вшит.

## Render (просто)
1. Залей файлы в репозиторий или напрямую.
2. Создай Web Service (Python).
3. **Environment**:
   - BOT_TOKEN = <твой токен бота>
   - TZ = Europe/Amsterdam (можно поменять)
   - PUSH_HOUR = 9
   - PUSH_MIN = 0
   - (необязательно) ADMIN_IDS = ещё ID через запятую
4. **Start Command**: `python bot.py`
5. Добавь Persistent Disk и примонтируй в `/app/data` (для сохранения БД).

## Локально
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # и впиши BOT_TOKEN
python bot.py
```

## Команды бота
- /start — меню
- /subscribe — включить ежедневную рассылку вопроса
- /unsubscribe — выключить рассылку
- /stats — краткая статистика

Папка `data/` создаётся автоматически. БД: `data/bot.sqlite3`.