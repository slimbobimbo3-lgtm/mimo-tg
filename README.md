# MiMo Code — Telegram Mini App

AI-ассистент для удалённого управления ПК через Telegram.

## Быстрая установка (Windows)

### 1. Установите зависимости

```bash
# Установите Python 3.11+ с python.org (галочка "Add to PATH")
# Установите Node.js с nodejs.org
```

### 2. Клонируйте проект

```bash
git clone <repo-url> mimo-tg
cd mimo-tg
```

### 3. Запустите установку

```bash
# Windows:
setup.bat

# Или вручную:
npm install -g mimocode
pip install -r requirements.txt
```

### 4. Настройте .env

Создайте файл `.env` в корне проекта:

```env
BOT_TOKEN=ваш_токен_от_BotFather
MIMO_URL=http://127.0.0.1:7860
NGROK_AUTHTOKEN=ваш_токен_ngrok
```

**Как получить токены:**

**Telegram Bot Token:**
1. Откройте @BotFather в Telegram
2. Отправьте `/newbot`
3. Придумайте имя и username
4. Скопируйте токен

**Ngrok Authtoken (опционально):**
1. Зарегистрируйтесь на ngrok.com
2. Скопируйте токен из Dashboard
3. Нужен для HTTPS (Telegram Mini App требует HTTPS)

### 5. Запустите

```bash
# Терминал 1 — mimo serve:
mimo serve --port 7860

# Терминал 2 — сервер:
python server.py
```

Или используйте `start.bat` (запускает всё автоматически).

### 6. Используйте

1. Откройте @ваш_бот в Telegram
2. Отправьте `/start`
3. Нажмите "Открыть MiMo App"
4. Готово!

## Автозапуск при включении ПК

```bash
# Добавьте в реестр (выполните в PowerShell):
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v MiMoBot /t REG_SZ /d "C:\path\to\start.bat" /f
```

## Структура проекта

```
mimo-tg/
├── server.py          # Основной сервер (FastAPI + bot + watchdog)
├── .env               # Конфигурация (НЕ коммитить!)
├── requirements.txt   # Python зависимости
├── setup.bat          # Установочный скрипт
├── start.bat          # Скрипт запуска
├── frontend/
│   └── index.html     # Telegram Mini App интерфейс
└── uploads/           # Загруженные файлы
```

## API эндпоинты

- `GET /api/sessions` — список сессий
- `POST /api/sessions` — создать сессию
- `GET /api/sessions/{id}/messages` — сообщения сессии
- `POST /api/chat` — отправить сообщение AI
- `GET /api/status` — статус ПК (CPU/RAM/GPU)
- `POST /api/terminal/start` — запустить команду
- `POST /api/terminal/stop` — остановить команду
- `GET /api/files` — список файлов
- `POST /api/files/upload` — загрузить файл

## Требования

- Windows 10/11
- Python 3.11+
- Node.js 18+
- NVIDIA GPU (опционально, для мониторинга GPU)
- Telegram аккаунт

## Устранение проблем

**"mimo CLI не найден":**
```bash
npm install -g mimocode
```

**"Ngrok failed":**
- Проверьте токен в .env
- Или используйте без ngrok (только по HTTP на локальной сети)

**"Telegram BadRequest: Only HTTPS":**
- Включите ngrok или настройте HTTPS
