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
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

db = sqlite3.connect("bot.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    url TEXT,
    reward INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS video_views (
    user_id INTEGER,
    video_id INTEGER,
    UNIQUE(user_id, video_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS deposits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    status TEXT DEFAULT 'pending'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS withdrawals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    method TEXT,
    number TEXT,
    status TEXT DEFAULT 'pending'
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


def change_balance(user_id, amount):
    add_user(user_id)
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, user_id)
    )
    db.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id)

    keyboard = [
        [InlineKeyboardButton("🎬 ভিডিও দেখুন", callback_data="videos")],
        [InlineKeyboardButton("💰 আমার ব্যালেন্স", callback_data="balance")],
        [InlineKeyboardButton("💳 ডিপোজিট", callback_data="deposit")],
        [InlineKeyboardButton("💸 উইথড্র", callback_data="withdraw")],
    ]

    await update.message.reply_text(
        f"স্বাগতম {user.first_name}! 🎉\n\n"
        "ভিডিও দেখে রিওয়ার্ড পয়েন্ট সংগ্রহ করুন।\n"
        "ডিপোজিট ও উইথড্র ম্যানুয়াল অনুমোদনের মাধ্যমে হবে।",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    add_user(user_id)

    if query.data == "balance":
        await query.edit_message_text(
            f"💰 আপনার বর্তমান ব্যালেন্স: {get_balance(user_id)} পয়েন্ট"
        )

    elif query.data == "videos":
        cursor.execute("SELECT id, title, url, reward FROM videos")
        videos = cursor.fetchall()

        if not videos:
            await query.edit_message_text(
                "🎬 এখনো কোনো ভিডিও যোগ করা হয়নি।"
            )
            return

        text = "🎬 ভিডিও সেকশন\n\n"
        keyboard = []

        for vid, title, url, reward in videos:
            text += f"🎥 {title}\n💰 রিওয়ার্ড: {reward} পয়েন্ট\n\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"▶️ {title}",
                    url=url
                ),
                InlineKeyboardButton(
                    "🎁 Claim",
                    callback_data=f"claim_{vid}"
                )
            ])

        await query.edit_message_text(
            text + "ভিডিও দেখে Claim বাটনে চাপুন।",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "deposit":
        await query.edit_message_text(
            "💳 ডিপোজিট\n\n"
            "ডিপোজিট করতে লিখুন:\n"
            "/deposit 100\n\n"
            "এরপর অ্যাডমিনের নির্দেশনা অনুযায়ী পেমেন্ট করুন।"
        )

    elif query.data == "withdraw":
        await query.edit_message_text(
            f"💸 উইথড্র\n\n"
            f"আপনার ব্যালেন্স: {get_balance(user_id)} পয়েন্ট\n\n"
            "উদাহরণ:\n"
            "/withdraw 100 bkash 01XXXXXXXXX"
        )

    elif query.data.startswith("claim_"):
        video_id = int(query.data.split("_")[1])

        cursor.execute(
            "SELECT reward FROM videos WHERE id = ?",
            (video_id,)
        )
        row = cursor.fetchone()

        if not row:
            await query.edit_message_text("ভিডিও পাওয়া যায়নি।")
            return

        reward = row[0]

        try:
            cursor.execute(
                "INSERT INTO video_views (user_id, video_id) VALUES (?, ?)",
                (user_id, video_id)
            )
            change_balance(user_id, reward)

            await query.edit_message_text(
                f"🎉 রিওয়ার্ড যোগ হয়েছে!\n\n"
                f"💰 +{reward} পয়েন্ট\n"
                f"বর্তমান ব্যালেন্স: {get_balance(user_id)} পয়েন্ট"
            )

        except sqlite3.IntegrityError:
            await query.edit_message_text(
                "⚠️ এই ভিডিওর রিওয়ার্ড আপনি আগে নিয়েছেন।"
            )

    elif query.data.startswith("approve_deposit_"):
        if user_id != ADMIN_ID:
            return

        deposit_id = int(query.data.split("_")[-1])

        cursor.execute(
            "SELECT user_id, amount FROM deposits WHERE id = ? AND status = 'pending'",
            (deposit_id,)
        )
        row = cursor.fetchone()

        if row:
            target_user, amount = row
            change_balance(target_user, amount)

            cursor.execute(
                "UPDATE deposits SET status = 'approved' WHERE id = ?",
                (deposit_id,)
            )
            db.commit()

            await query.edit_message_text("✅ ডিপোজিট অনুমোদন করা হয়েছে।")
            await context.bot.send_message(
                target_user,
                f"💳 আপনার ডিপোজিট অনুমোদিত হয়েছে!\n"
                f"💰 +{amount} পয়েন্ট"
            )

    elif query.data.startswith("approve_withdraw_"):
        if user_id != ADMIN_ID:
            return

        withdraw_id = int(query.data.split("_")[-1])

        cursor.execute(
            "SELECT user_id, amount, method, number FROM withdrawals "
            "WHERE id = ? AND status = 'pending'",
            (withdraw_id,)
        )
        row = cursor.fetchone()

        if row:
            target_user, amount, method, number = row

            if get_balance(target_user) < amount:
                await query.edit_message_text("❌ ব্যবহারকারীর পর্যাপ্ত ব্যালেন্স নেই।")
                return

            change_balance(target_user, -amount)

            cursor.execute(
                "UPDATE withdrawals SET status = 'approved' WHERE id = ?",
                (withdraw_id,)
            )
            db.commit()

            await query.edit_message_text("✅ উইথড্র অনুমোদন করা হয়েছে।")
            await context.bot.send_message(
                target_user,
                f"💸 আপনার উইথড্র অনুমোদিত হয়েছে!\n"
                f"💰 -{amount} পয়েন্ট"
            )


async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)

    if not context.args:
        await update.message.reply_text(
            "উদাহরণ: /deposit 100"
        )
        return

    try:
        amount = int(context.args[0])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("সঠিক অ্যামাউন্ট দিন।")
        return

    cursor.execute(
        "INSERT INTO deposits (user_id, amount) VALUES (?, ?)",
        (user_id, amount)
    )
    deposit_id = cursor.lastrowid
    db.commit()

    await update.message.reply_text(
        f"💳 ডিপোজিট রিকোয়েস্ট নেওয়া হয়েছে।\n"
        f"💰 অ্যামাউন্ট: {amount} টাকা\n\n"
        "অ্যাডমিন পেমেন্ট যাচাই করে অনুমোদন করবেন।"
    )

    if ADMIN_ID:
        keyboard = [[
            InlineKeyboardButton(
                "✅ Approve",
                callback_data=f"approve_deposit_{deposit_id}"
            )
        ]]

        await context.bot.send_message(
            ADMIN_ID,
            f"💳 নতুন ডিপোজিট রিকোয়েস্ট\n\n"
            f"User ID: {user_id}\n"
            f"Amount: {amount} টাকা",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)

    if len(context.args) < 3:
        await update.message.reply_text(
            "উদাহরণ:\n/withdraw 100 bkash 01XXXXXXXXX"
        )
        return

    try:
        amount = int(context.args[0])
        method = context.args[1]
        number = context.args[2]

        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("সঠিক তথ্য দিন।")
        return

    if get_balance(user_id) < amount:
        await update.message.reply_text(
            "❌ আপনার পর্যাপ্ত ব্যালেন্স নেই।"
        )
        return

    cursor.execute(
        "INSERT INTO withdrawals (user_id, amount, method, number) "
        "VALUES (?, ?, ?, ?)",
        (user_id, amount, method, number)
    )
    withdraw_id = cursor.lastrowid
    db.commit()

    await update.message.reply_text(
        f"💸 উইথড্র রিকোয়েস্ট নেওয়া হয়েছে।\n"
        f"💰 অ্যামাউন্ট: {amount} পয়েন্ট\n"
        f"📱 পদ্ধতি: {method}\n"
        f"📞 নম্বর: {number}\n\n"
        "অ্যাডমিন অনুমোদন করবেন।"
    )

    if ADMIN_ID:
        keyboard = [[
            InlineKeyboardButton(
                "✅ Approve",
                callback_data=f"approve_withdraw_{withdraw_id}"
            )
        ]]

        await context.bot.send_message(
            ADMIN_ID,
            f"💸 নতুন উইথড্র রিকোয়েস্ট\n\n"
            f"User ID: {user_id}\n"
            f"Amount: {amount}\n"
            f"Method: {method}\n"
            f"Number: {number}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def addvideo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "উদাহরণ:\n"
            "/addvideo ভিডিওর_নাম https://example.com/video 10"
        )
        return

    title = context.args[0]
    url = context.args[1]
    reward = int(context.args[2])

    cursor.execute(
        "INSERT INTO videos (title, url, reward) VALUES (?, ?, ?)",
        (title, url, reward)
    )
    db.commit()

    await update.message.reply_text("✅ ভিডিও যোগ হয়েছে।")


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN সেট করা হয়নি।")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("deposit", deposit))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CommandHandler("addvideo", addvideo))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
