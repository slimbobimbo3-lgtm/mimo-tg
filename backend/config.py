import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN", "")
MIMO_URL = os.getenv("MIMO_URL", "http://127.0.0.1:7860")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
