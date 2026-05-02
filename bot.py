from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import json, os

TOKEN = "8309524127:AAH0ntYzDJaxWBQzslaSK7svO5sctoO9Wxs"
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
        "Привет! Я помогу не пропустить дедлайны 🎓\nВыбери действие:",
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
            msg = "Твои дедлайны:\n\n"
            for i, d in enumerate(data[user_id], 1):
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
        await update.message.reply_text("Теперь напиши дату (например: 20 мая или 2025-05-20):")

    elif context.user_data.get("waiting_for") == "date":
        name = context.user_data.get("deadline_name", "Без названия")
        data[user_id].append({"name": name, "date": text})
        save_data(data)
        context.user_data["waiting_for"] = None
        await update.message.reply_text(
            f"Дедлайн добавлен:\n{name} — {text}",
            reply_markup=main_menu()
        )

    elif context.user_data.get("waiting_for") == "delete":
        try:
            index = int(text) - 1
            removed = data[user_id].pop(index)
            save_data(data)
            await update.message.reply_text(
                f"Удалено: {removed['name']} — {removed['date']}",
                reply_markup=main_menu()
            )
        except:
            await update.message.reply_text("Напиши просто номер из списка, например: 1")
        context.user_data["waiting_for"] = None

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен! Нажми Ctrl+C чтобы остановить.")
    app.run_polling()
ы