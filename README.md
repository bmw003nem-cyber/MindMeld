# MindMeld — FINAL (single-file + keep-alive HTTP)

Мы оставляем тип сервиса **Web Service** на Render и используем встроенный `keep-alive` HTTP-сервер,
чтобы пингер (UptimeRobot) видел живой порт. Основная логика бота — `run_polling()`.

## Что внутри
- `bot.py` — единый файл с ботом и HTTP keep-alive.
- `requirements.txt` — зависимости (python-telegram-bot + Flask + pytz).

## Что настроить на Render
1) **Environment → BOT_TOKEN** — токен от @BotFather.
2) **Start Command**: `python bot.py`
3) В репозитории должны лежать:
   - `assets/welcome.jpg`, `assets/qr.png`
   - `guide_path_to_self.pdf`, `guide_know_but_dont_do.pdf`, `guide_self_acceptance.pdf`, `guide_shut_the_mind.pdf`
4) Если были старые процессы: сделай **Manual Deploy → Clear build cache & deploy**.

## Healthcheck для пингера
- URL: `https://<твоё_имя>.onrender.com/health`
