import os, psycopg2
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TOKEN", "8309524127:AAH0ntYzDJaxWBQzslaSK7svO5sctoO9Wxs")
DATABASE_URL = os.environ.get("DATABASE_URL")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "deadline_kz_bot")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS deadlines (
            id SERIAL PRIMARY KEY,
            user_id TEXT,
            chat_id BIGINT,
            name TEXT,
            date TEXT,
            done BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            referred_by TEXT,
            referral_count INT DEFAULT 0,
            joined_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def main_menu():
    keyboard = [
        ["📋 Мои дедлайны", "➕ Добавить дедлайн"],
        ["✅ Выполнено", "🗑 Удалить дедлайн"],
        ["📊 Статистика", "👥 Пригласить друга"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username or "unknown"
    
    # Проверяем реферальный код
    referred_by = None
    if context.args:
        referred_by = context.args[0]
        if referred_by == user_id:
            referred_by = None  # нельзя пригласить себя

    conn = get_conn()
    cur = conn.cursor()
    
    # Проверяем новый ли пользователь
    cur.execute("SELECT user_id FROM users WHERE user_id=%s", (user_id,))
    existing = cur.fetchone()
    
    if not existing:
        # Новый пользователь
        cur.execute(
            "INSERT INTO users (user_id, username, referred_by) VALUES (%s, %s, %s)",
            (user_id, username, referred_by)
        )
        # Начисляем +1 пригласившему
        if referred_by:
            cur.execute(
                "UPDATE users SET referral_count = referral_count + 1 WHERE user_id=%s",
                (referred_by,)
            )
            conn.commit()
            # Уведомляем пригласившего
            try:
                await context.bot.send_message(
                    chat_id=int(referred_by),
                    text=f"🎉 По твоей ссылке зарегистрировался новый пользователь!\nТвои приглашения растут 📈"
                )
            except:
                pass
    
    conn.commit()
    cur.close()
    conn.close()

    await update.message.reply_text(
        "Привет! Я помогу не пропустить дедлайны 🎓\n"
        "Дату добавляй в формате ДД.ММ.ГГГГ\n"
        "Например: 20.05.2026\n\nВыбери действие:",
        reply_markup=main_menu()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.message.from_user.id)
    chat_id = update.message.chat_id

    if text == "📋 Мои дедлайны":
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, date FROM deadlines WHERE user_id=%s AND done=FALSE ORDER BY date",
            (user_id,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if not rows:
            await update.message.reply_text("У тебя пока нет дедлайнов. Нажми ➕ чтобы добавить.")
        else:
            today = datetime.now().date()
            msg = "Твои дедлайны:\n\n"
            for row in rows:
                rid, name, date = row
                try:
                    d = datetime.strptime(date, "%d.%m.%Y").date()
                    days = (d - today).days
                    if days < 0: status = "❌ просрочен"
                    elif days == 0: status = "🔴 сегодня!"
                    elif days == 1: status = "🟠 завтра!"
                    elif days <= 3: status = f"🟡 через {days} дня"
                    else: status = f"🟢 через {days} дней"
                except:
                    status = ""
                msg += f"#{rid} {name} — {date} {status}\n"
            await update.message.reply_text(msg)

    elif text == "➕ Добавить дедлайн":
        context.user_data["waiting_for"] = "name"
        await update.message.reply_text("Напиши название задачи:")

    elif text == "✅ Выполнено":
        context.user_data["waiting_for"] = "done"
        await update.message.reply_text("Напиши номер (#) выполненного дедлайна:")

    elif text == "🗑 Удалить дедлайн":
        context.user_data["waiting_for"] = "delete"
        await update.message.reply_text("Напиши номер (#) дедлайна который хочешь удалить:")

    elif text == "📊 Статистика":
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM deadlines WHERE user_id=%s", (user_id,))
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM deadlines WHERE user_id=%s AND done=TRUE", (user_id,))
        done = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM deadlines WHERE user_id=%s AND done=FALSE", (user_id,))
        active = cur.fetchone()[0]
        cur.execute("SELECT referral_count FROM users WHERE user_id=%s", (user_id,))
        ref_row = cur.fetchone()
        referrals = ref_row[0] if ref_row else 0
        cur.close()
        conn.close()
        await update.message.reply_text(
            f"📊 Твоя статистика:\n\n"
            f"Всего дедлайнов: {total}\n"
            f"✅ Выполнено: {done}\n"
            f"⏳ Активных: {active}\n"
            f"👥 Приглашено друзей: {referrals}\n\n"
            f"Так держать! 💪"
        )

    elif text == "👥 Пригласить друга":
        ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        await update.message.reply_text(
            f"👥 Твоя реферальная ссылка:\n\n"
            f"{ref_link}\n\n"
            f"Отправь её друзьям-студентам!\n"
            f"Когда они зарегистрируются — ты получишь уведомление 🎉"
        )

    elif context.user_data.get("waiting_for") == "name":
        context.user_data["deadline_name"] = text
        context.user_data["waiting_for"] = "date"
        await update.message.reply_text("Теперь напиши дату (ДД.ММ.ГГГГ):")

    elif context.user_data.get("waiting_for") == "date":
        try:
            datetime.strptime(text, "%d.%m.%Y")
            name = context.user_data.get("deadline_name", "Без названия")
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO deadlines (user_id, chat_id, name, date) VALUES (%s, %s, %s, %s)",
                (user_id, chat_id, name, text)
            )
            conn.commit()
            cur.close()
            conn.close()
            context.user_data["waiting_for"] = None
            await update.message.reply_text(
                f"✅ Дедлайн добавлен:\n{name} — {text}\n\nПришлю напоминание за день до срока!",
                reply_markup=main_menu()
            )
        except ValueError:
            await update.message.reply_text("Неверный формат. Напиши так: 20.05.2026")

    elif context.user_data.get("waiting_for") == "done":
        try:
            rid = int(text.replace("#", ""))
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("UPDATE deadlines SET done=TRUE WHERE id=%s AND user_id=%s", (rid, user_id))
            conn.commit()
            cur.close()
            conn.close()
            context.user_data["waiting_for"] = None
            await update.message.reply_text("✅ Выполнено! Молодец 🎉", reply_markup=main_menu())
        except:
            await update.message.reply_text("Напиши просто номер, например: 3")

    elif context.user_data.get("waiting_for") == "delete":
        try:
            rid = int(text.replace("#", ""))
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM deadlines WHERE id=%s AND user_id=%s", (rid, user_id))
            conn.commit()
            cur.close()
            conn.close()
            context.user_data["waiting_for"] = None
            await update.message.reply_text("🗑 Удалено.", reply_markup=main_menu())
        except:
            await update.message.reply_text("Напиши просто номер, например: 3")

async def check_deadlines(context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    cur = conn.cursor()
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    cur.execute("SELECT chat_id, name, date FROM deadlines WHERE done=FALSE")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    for chat_id, name, date in rows:
        try:
            d = datetime.strptime(date, "%d.%m.%Y").date()
            if d == tomorrow:
                await context.bot.send_message(chat_id=chat_id, text=f"⏰ Завтра дедлайн:\n{name} — {date}\n\nНе забудь!")
            elif d == today:
                await context.bot.send_message(chat_id=chat_id, text=f"🔴 Сегодня дедлайн:\n{name}\n\nПоследний день!")
        except:
            continue

if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    job_queue = app.job_queue
    job_queue.run_daily(check_deadlines, time=datetime.strptime("09:00", "%H:%M").time())
    print("Бот запущен с реферальной системой!")
    app.run_polling()