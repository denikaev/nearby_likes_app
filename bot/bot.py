import os
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://example.com/webapp")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[
        KeyboardButton(text="Открыть Nearby Likes", web_app=WebAppInfo(url=WEBAPP_URL))
    ]]
    await update.message.reply_text(
        "Открой мини-апп, разреши геолокацию и лайкай только тех, кто реально рядом (≤ 50 м).",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == "__main__":
    main()
