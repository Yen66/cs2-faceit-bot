import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
FACEIT_API_KEY = os.getenv("FACEIT_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env")
if not FACEIT_API_KEY:
    raise ValueError("FACEIT_API_KEY is not set in .env")
