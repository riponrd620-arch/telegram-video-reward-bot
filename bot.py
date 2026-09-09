import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.getenv("BOT_TOKEN")

# Database
db = sqlite3.connect("bot.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
)
""")
db.commit()


def add_user(user_id):
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)",
        (user_id,)
    )
    db.commit()


def get_balance(user_id):
    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id)

    keyboard = [
        [InlineKeyboardButton("🎬 ভিডিও দেখুন", callback_data="videos")],
        [InlineKeyboardButton("💰 আমার ব্যালেন্স", callback_data="balance")],
        [InlineKeyboardButton("💸 রিওয়ার্ড রিডিম", callback_data="withdraw")],
    ]

    await update.message.reply_text(
        f"স্বাগতম {user.first_name}! 🎉\n\n"
        "ভিডিও দেখে রিওয়ার্ড পয়েন্ট সংগ্রহ করুন।",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    add_user(user_id)

    if query.data == "balance":
        balance = get_balance(user_id)

        await query.edit_message_text(
            f"💰 আপনার বর্তমান ব্যালেন্স: {balance} পয়েন্ট"
        )

    elif query.data == "videos":
        await query.edit_message_text(
            "🎬 ভিডিও সেকশন\n\n"
            "এখানে পরে অ্যাডমিন যোগ করা ভিডিও দেখানো হবে।\n"
            "ভিডিও সম্পূর্ণ দেখার পর রিওয়ার্ড দেওয়া হবে।"
        )

    elif query.data == "withdraw":
        balance = get_balance(user_id)

        await query.edit_message_text(
            f"💸 রিওয়ার্ড রিডিম\n\n"
            f"আপনার ব্যালেন্স: {balance} পয়েন্ট\n\n"
            "ন্যূনতম রিডিম সীমা পরে অ্যাডমিন সেট করতে পারবে।"
        )


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN সেট করা হয়নি।")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()