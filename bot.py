import os
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

load_dotenv()

# ដាក់ Token ពិតប្រាកដរបស់អ្នកជា Default បើសិនជា Railway រក Environment Variable មិនឃើញ
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8728776324:AAGWZ3MX7e2SKLEyU85OEni5P73y_00fo"
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID") or "6703552603"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Database Setup
def init_db():
    conn = sqlite3.connect("tracker.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_activity (
            group_id INTEGER PRIMARY KEY,
            group_title TEXT,
            last_active TIMESTAMP,
            today_messages INTEGER DEFAULT 0,
            today_photos INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def log_activity(chat_id: int, title: str, is_photo: bool = False):
    conn = sqlite3.connect("tracker.db")
    cursor = conn.cursor()
    now = datetime.now()
    
    cursor.execute("""
        INSERT INTO group_activity (group_id, group_title, last_active, today_messages, today_photos)
        VALUES (?, ?, ?, 1, ?)
        ON CONFLICT(group_id) DO UPDATE SET
            group_title = excluded.group_title,
            last_active = excluded.last_active,
            today_messages = today_messages + 1,
            today_photos = today_photos + excluded.today_photos
    """, (chat_id, title, now, 1 if is_photo else 0))
    
    conn.commit()
    conn.close()

# Handler សម្រាប់ចាប់ Message គ្រប់ Group
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def track_messages(message: types.Message):
    is_photo = bool(message.photo or message.document)
    log_activity(message.chat.id, message.chat.title or "Unknown Group", is_photo)

# បង្កើតរបាយការណ៍
def generate_report_text():
    conn = sqlite3.connect("tracker.db")
    cursor = conn.cursor()
    cursor.execute("SELECT group_title, last_active, today_messages, today_photos FROM group_activity")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "មិនទាន់មានទិន្នន័យសកម្មភាពនៅឡើយទេ។"

    now = datetime.now()
    active_list = []
    inactive_list = []

    for title, last_active_str, msg_count, photo_count in rows:
        last_active = datetime.fromisoformat(last_active_str)
        diff_hours = (now - last_active).total_seconds() / 3600

        # ចាត់ទុកថា Inactive បើលើសពី ២៤ម៉ោង ឬ គ្មានសារថ្ងៃនេះ
        if diff_hours >= 24 or msg_count == 0:
            inactive_list.append(f"• <b>{title}</b> (សកម្មភាពចុងក្រោយ: {last_active.strftime('%d/%m %H:%M')})")
        else:
            active_list.append(f"• <b>{title}</b>: {msg_count} សារ (រូប/ឯកសារ: {photo_count})")

    report = f"📊 <b>របាយការណ៍សកម្មភាពប្រចាំថ្ងៃ ({now.strftime('%d/%m/%Y')})</b>\n\n"
    
    report += "✅ <b>ថ្នាក់ដែលមានសកម្មភាព:</b>\n"
    report += "\n".join(active_list) if active_list else "គ្មាន"
    
    report += "\n\n⚠️ <b>ថ្នាក់ដែលអសកម្ម (លើសពី ២៤ម៉ោង):</b>\n"
    report += "\n".join(inactive_list) if inactive_list else "គ្មាន"

    return report

# Function ផ្ញើ Report ស្វ័យប្រវត្តិ
async def send_daily_report():
    if ADMIN_CHAT_ID:
        report = generate_report_text()
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=report, parse_mode="HTML")
        
        # Reset ការរាប់ប្រចាំថ្ងៃ
        conn = sqlite3.connect("tracker.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE group_activity SET today_messages = 0, today_photos = 0")
        conn.commit()
        conn.close()

# Command សម្រាប់ Admin មើលរបាយការណ៍ភ្លាមៗ
@dp.message(Command("report"))
async def manual_report(message: types.Message):
    if str(message.chat.id) == str(ADMIN_CHAT_ID) or message.chat.type == "private":
        report = generate_report_text()
        await message.answer(report, parse_mode="HTML")

async def main():
    init_db()
    # កំណត់ម៉ោងផ្ញើ Report រៀងរាល់ម៉ោង 5:30 ល្ងាច
    scheduler.add_job(send_daily_report, 'cron', hour=17, minute=30)
    scheduler.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
