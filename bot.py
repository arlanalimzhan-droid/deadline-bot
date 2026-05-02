from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, JobQueue
import json, os
from datetime import datetime, timedelta

TOKEN = os.environ.get("TOKEN", "8309524127:AAH0ntYzDJaxWBQzslaSK7svO5sctoO9Wxs")
DATA_FILE = "deadlines.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main_menu():
    keyboard = [["📋 Мои дедлайны", "➕ Добавить дедлайн"], ["🗑 Удалить дедлайн"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я помогу не пропустить дедлайны 🎓\n"
        "Добавляй задачи в формате даты: ДД.ММ.ГГГГ\n"
        "Например: 20.05.2025\n\nВыбери действие:",
        reply_markup=main_menu()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.message.from_user.id)
    data = load_data()

    if user_id not in data:
        data[user_id] = []

    if text == "📋 Мои дедлайны":
        if not data[user_id]:
            await update.message.reply_text("У тебя пока нет дедлайнов. Нажми ➕ чтобы добавить.")
        else:
            today = datetime.now().date()
            msg = "Твои дедлайны:\n\n"
            for i, d in enumerate(data[user_id], 1):
                try:
                    deadline_date = datetime.strptime(d['date'], "%d.%m.%Y").date()
                    days_left = (deadline_date - today).days
                    if days_left < 0:
                        status = "❌ просрочен"
                    elif days_left == 0:
                        status = "🔴 сегодня!"
                    elif days_left == 1:
                        status = "🟠 завтра!"
                    elif days_left <= 3:
                        status = f"🟡 через {days_left} дня"
                    else:
                        status = f"🟢 через {days_left} дней"
                    msg += f"{i}. {d['name']} — {d['date']} ({status})\n"
                except:
                    msg += f"{i}. {d['name']} — {d['date']}\n"
            await update.message.reply_text(msg)

    elif text == "➕ Добавить дедлайн":
        context.user_data["waiting_for"] = "name"
        await update.message.reply_text("Напиши название задачи (например: Курсовая по экономике):")

    elif text == "🗑 Удалить дедлайн":
        if not data[user_id]:
            await update.message.reply_text("Нечего удалять — список пуст.")
        else:
            msg = "Напиши номер дедлайна который хочешь удалить:\n\n"
            for i, d in enumerate(data[user_id], 1):
                msg += f"{i}. {d['name']} — {d['date']}\n"
            context.user_data["waiting_for"] = "delete"
            await update.message.reply_text(msg)

    elif context.user_data.get("waiting_for") == "name":
        context.user_data["deadline_name"] = text
        context.user_data["waiting_for"] = "date"
        await update.message.reply_text(
            "Теперь напиши дату в формате ДД.ММ.ГГГГ\n"
            "Например: 20.05.2025"
        )

    elif context.user_data.get("waiting_for") == "date":
        try:
            datetime.strptime(text, "%d.%m.%Y")
            name = context.user_data.get("deadline_name", "Без названия")
            data[user_id].append({"name": name, "date": text, "chat_id": update.message.chat_id})
            save_data(data)
            context.user_data["waiting_for"] = None
            await update.message.reply_text(
                f"✅ Дедлайн добавлен:\n{name} — {text}\n\nПришлю напоминание за день до срока!",
                reply_markup=main_menu()
            )
        except ValueError:
            await update.message.reply_text("Неверный формат. Напиши дату так: 20.05.2025")

    elif context.user_data.get("waiting_for") == "delete":
        try:
            index = int(text) - 1
            removed = data[user_id].pop(index)
            save_data(data)
            await update.message.reply_text(
                f"🗑 Удалено: {removed['name']} — {removed['date']}",
                reply_markup=main_menu()
            )
        except:
            await update.message.reply_text("Напиши просто номер из списка, например: 1")
        context.user_data["waiting_for"] = None

async def check_deadlines(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)

    for user_id, deadlines in data.items():
        for d in deadlines:
            try:
                deadline_date = datetime.strptime(d['date'], "%d.%m.%Y").date()
                chat_id = d.get("chat_id")
                if not chat_id:
                    continue
                if deadline_date == tomorrow:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"⏰ Напоминание!\n\nЗавтра дедлайн: {d['name']}\nДата: {d['date']}\n\nНе забудь!"
                    )
                elif deadline_date == today:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"🔴 Сегодня дедлайн: {d['name']}\n\nПоследний день!"
                    )
            except:
                continue

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Проверка дедлайнов каждый день в 9:00
    job_queue = app.job_queue
    job_queue.run_daily(check_deadlines, time=datetime.strptime("09:00", "%H:%M").time())
    
    print("Бот запущен с напоминаниями!")
    app.run_polling()