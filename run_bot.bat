@echo off
cd /d C:\Users\123\mimo-tg
python -m uvicorn server:app --host 0.0.0.0 --port 8765 > bot.log 2>&1