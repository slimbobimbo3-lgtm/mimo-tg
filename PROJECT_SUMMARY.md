# MiMo Telegram Mini App — Итоговый отчёт

## Дата: 15 июня 2026

---

## Что было сделано

### Telegram Mini App бот
Бот `@mimo1ai_bot` для удалённого управления ПК через Telegram. Был создан с нуля за несколько дней.

**Ключевые фичи:**
- Чат с AI (MiMo Code) через `mimo serve` API
- Мониторинг ПК в реальном времени (CPU/RAM/GPU/VRAM)
- Терминал с live-выводом
- Загрузка файлов и фото (drag & drop)
- Удаление и создание сессий
- SSE streaming — ответы появляются в реальном времени
- Индикаторы статуса: "Отправляю...", "Думаю...", "Пишу...", "Готово"
- Tool calls отображаются внутри сообщений
- Токены контекста (из 1M) показываются при наведении на сессию

**Команды бота:**
- `/start` — открыть Mini App
- `/save [описание]` — сохранить версию кода
- `/versions` — список сохранённых версий
- `/restore_N` — откатиться на версию N

### Архитектура
```
Telegram → ngrok/Cloudflare → FastAPI (порт 8765) → mimo serve (порт 7860)
                                    ↓
                              Фронтенд (HTML/CSS/JS)
                              Мониторинг (nvidia-smi)
                              Загрузка файлов
                              SSE streaming
                              Watchdog
```

**Бэкенд:** Python (FastAPI + aiogram 3)
**Фронтенд:** Vanilla HTML/CSS/JS с SSE streaming
**Туннель:** ngrok (бесплатный) или Cloudflare (нужен VC++ runtime)
**Автозапуск:** Windows Registry + start.bat

### Промо-сайт
Одностраничный сайт для продвижения бота в стиле 8bit.ai:
- Flowing секции с scroll-reveal анимациями
- Marquee строка
- Градиентный текст
- Кнопка "Открыть бота" → t.me/mimo1ai_bot

### Запуск на 3 дня (дача)
- Автозапуск при ребуте Windows (реестр HKCU\Run)
- Watchdog mimo serve (каждые 30 сек)
- Watchdog ngrok (каждые 5 мин)
- start.bat: Kakadu VPN → mimo serve → server.py

---

## Проблемы и решения

1. **mimo CLI не найден** — npm .cmd файлы не работают с `create_subprocess_exec`, исправлено на `shell=True`
2. **Сессии-мусор** — фильтрация checkpoint-writer и подсессий
3. **Бот не стартует** — ngrok не успевает подняться, добавлено ожидание 60 сек
4. **Чат не обновляется** — polling с `msgCount` заменён на SSE streaming
5. **isSending застревает** — добавлен таймаут сброса 120 сек
6. **SSE обрывается** — добавлен reconnect с прогрессивной задержкой и health check

---

## Файлы проекта
- `server.py` — основной сервер (FastAPI + bot + watchdog + SSE proxy)
- `frontend/index.html` — Mini App интерфейс
- `.env` — конфигурация (НЕ коммитить!)
- `start.bat` — автозапуск
- `setup.bat` — автоустановка для новых пользователей
- `README.md` — инструкция

---

## Ссылки
- **GitHub:** https://github.com/slimbobimbo3-lgtm/mimo-tg
- **Бот:** https://t.me/mimo1ai_bot
- **Ngrok URL:** https://discuss-crowd-curable.ngrok-free.dev (может измениться)

---

## Что нужно доработать
1. Cloudflare Tunnel вместо ngrok (нужен Visual C++ runtime)
2. Персистентный ngrok URL (Cloudflare Named Tunnel или paid ngrok)
3. Более стабильный polling/reconnect
4. Многопользовательская поддержка (каждый ставит у себя)
5. Улучшение дизайна (референсы: 8bit.ai, floema.com, helloelva.com)

---

*Проект создан совместно с MiMo Code, 11-15 июня 2026*
