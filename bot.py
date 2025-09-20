import asyncio
import random
import datetime
import pytz
from collections import defaultdict

from telegram import Update, Message
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# === Настройки ===
TOKEN = "7684439594:AAGE58iJTS1V-wjiKFdViAmcVKyImUnr15Y"
MINSK_TZ = pytz.timezone("Europe/Minsk")

# Чаты и допустимые треды
ALLOWED_TOPICS = {
    -1002079167705: 48,
    -1002936236597: 3,
    -1002423500927: 2,
    -1002535060344: 5,
    -1002477650634: 3,
    -1002660511483: 3,
    -1002864795738: 3,
    -1002360529455: 3,
    -1002538985387: 3,
}

# Фразы
WARNING_MESSAGES = [
    "Минуточку! Этот раздел не для всех. Я тут слежу за порядком и вынужден принять меры: на первый раз — предупреждение!",
    "Эй! Это место только для отчётов о доставке. Пожалуйста, не отвлекайся!",
    "Порядок — моё второе имя. Сообщение не по теме — предупреждение!",
    "Осторожно, ты вторгся на территорию отчётов. Будь внимательнее в следующий раз!",
    "Это место для отчётности, а не обсуждений. Попрошу соблюдать правила!",
    "Каждое лишнее слово может стоить порядка. Предупреждение!",
    "Опа! Нарушение регламента. Надеюсь, это в последний раз."
]

REMINDER_FOR_MINUS = (
    "Вижу, что заказ не состоялся. Не забудьте описать ситуацию в разделе «изменения обстоятельств доставок». "
    "Это сообщение будет удалено через 10 минут."
)

# Хранилище
plus_records = defaultdict(list)
warning_counts = defaultdict(int)

# === Обработка сообщений ===
async def monitor_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message: Message = update.message
    text = message.text or ""
    chat_id = message.chat_id
    thread_id = message.message_thread_id
    user_id = message.from_user.id
    username = message.from_user.full_name

    if chat_id in ALLOWED_TOPICS and thread_id in ALLOWED_TOPICS[chat_id]:
        if "+" in text:
            plus_records[(chat_id, thread_id)].append(datetime.datetime.now(tz=MINSK_TZ))
            print(f"[LOG] + записан: {chat_id}/{thread_id}")
        elif text.strip() == "-":
            reply = await message.reply_text(REMINDER_FOR_MINUS)
            await asyncio.sleep(600)  # 10 минут
            try:
                await message.delete()
                await reply.delete()
            except Exception as e:
                print(f"[ERROR] Удаление '-' сообщения: {e}")
        else:
            # Нарушение
            warning_text = random.choice(WARNING_MESSAGES)
            warning = await message.reply_text(warning_text)

            # Счётчик
            warning_counts[user_id] += 1
            count = warning_counts[user_id]
            print(f"[WARN] {username} получил предупреждение ({count}/3)")

            # Удаление через 15 секунд
            await asyncio.sleep(15)
            try:
                await message.delete()
                await warning.delete()
            except Exception as e:
                print(f"[ERROR] Удаление нарушающего сообщения: {e}")

# === Ежедневный отчёт ===
async def report_daily_plus(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now(tz=MINSK_TZ)
    yesterday = now.date() - datetime.timedelta(days=1)

    for (chat_id, thread_id), timestamps in plus_records.items():
        count = sum(1 for t in timestamps if t.date() == yesterday)
        if count > 0:
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    message_thread_id=thread_id,
                    text=f"📦 Итого выполнено заказов: {count}"
                )
                print(f"[LOG] Отчёт {count} отправлен в {chat_id}/{thread_id}")
            except Exception as e:
                print(f"[ERROR] Не удалось отправить отчёт: {e}")

# === Запуск ===
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), monitor_section))

    loop = asyncio.get_event_loop()
    scheduler = AsyncIOScheduler(timezone=MINSK_TZ, event_loop=loop)
    trigger = CronTrigger(hour=23, minute=0)
    scheduler.add_job(report_daily_plus, trigger, args=[app.bot])
    scheduler.start()

    print("[INFO] Бот запущен...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
