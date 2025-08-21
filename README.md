# MindMeld — FINISHED (single-file)

**Что внутри**
- `bot.py` — единый файл бота.
- `requirements.txt` — зависимости.

**Как это работает**
- `BOT_TOKEN` берётся из переменных окружения Render (Environment → `BOT_TOKEN`).
- Все ссылки/юзернеймы уже зашиты в код: ничего руками не вписывать.

**Файлы, которые должны лежать рядом (как у тебя в репо уже есть):**
- PDF: `guide_path_to_self.pdf`, `guide_know_but_dont_do.pdf`, `guide_self_acceptance.pdf`, `guide_shut_the_mind.pdf`
- Картинки: `assets/welcome.jpg`, `assets/qr.png`

**Запуск локально (если нужно):**
```
pip install -r requirements.txt
export BOT_TOKEN=XXX   # или set BOT_TOKEN=XXX на Windows
python bot.py
```
