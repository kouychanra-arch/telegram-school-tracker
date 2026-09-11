import os
import re
import sqlite3
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8728776324:AAGWZ3MX7e2SKLEyU85OEni5P73y_00fo"
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID") or "6703552603"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Setup Database & Auto-Migration
def init_db():
    conn = sqlite3.connect("tracker.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_activity (
            group_id INTEGER PRIMARY KEY,
            group_title TEXT,
            last_active TEXT,
            today_messages INTEGER DEFAULT 0,
            today_photos INTEGER DEFAULT 0,
            count_text INTEGER DEFAULT 0,
            count_voice INTEGER DEFAULT 0,
            count_photo INTEGER DEFAULT 0,
            count_video INTEGER DEFAULT 0,
            count_file INTEGER DEFAULT 0,
            count_link INTEGER DEFAULT 0
        )
    """)
    conn.commit()

    # បន្ថែម columns ស្វ័យប្រវត្តិប្រសិនបើជា database ចាស់
    columns_to_add = [
        ("count_text", "INTEGER DEFAULT 0"),
        ("count_voice", "INTEGER DEFAULT 0"),
        ("count_photo", "INTEGER DEFAULT 0"),
        ("count_video", "INTEGER DEFAULT 0"),
        ("count_file", "INTEGER DEFAULT 0"),
        ("count_link", "INTEGER DEFAULT 0")
    ]
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE group_activity ADD COLUMN {col_name} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    conn.close()

# កត់ត្រាសកម្មភាពចូល Database
def log_activity(chat_id: int, title: str, msg_type: str):
    conn = sqlite3.connect("tracker.db")
    cursor = conn.cursor()
    now_str = datetime.now().isoformat()
    col = f"count_{msg_type}"

    cursor.execute("SELECT group_id FROM group_activity WHERE group_id = ?", (chat_id,))
    row = cursor.fetchone()

    if row:
        cursor.execute(f"""
            UPDATE group_activity 
            SET group_title = ?, 
                last_active = ?, 
                today_messages = COALESCE(today_messages, 0) + 1, 
                {col} = COALESCE({col}, 0) + 1
            WHERE group_id = ?
        """, (title, now_str, chat_id))
    else:
        cursor.execute(f"""
            INSERT INTO group_activity (group_id, group_title, last_active, today_messages, {col})
            VALUES (?, ?, ?, 1, 1)
        """, (chat_id, title, now_str))

    conn.commit()
    conn.close()

# Handler ចាប់សារគ្រប់ប្រភេទក្នុង Group
@dp.message()
async def track_messages(message: types.Message):
    # មិនចាប់សារក្នុង Chat ផ្ទាល់ខ្លួនឡើយ
    if message.chat.type not in ["group", "supergroup"]:
        return

    title = message.chat.title or "Unknown Group"

    try:
        if message.voice or message.audio:
            log_activity(message.chat.id, title, "voice")
        elif message.photo:
            log_activity(message.chat.id, title, "photo")
        elif message.video or message.video_note or message.animation:
            log_activity(message.chat.id, title, "video")
        elif message.document:
            log_activity(message.chat.id, title, "file")
        else:
            text = message.text or message.caption or ""
            url_pattern = r'(https?://\S+|www\.\S+)'
            if re.search(url_pattern, text):
                log_activity(message.chat.id, title, "link")
            else:
                log_activity(message.chat.id, title, "text")
    except Exception as e:
        print(f"Error logging message: {e}")

def is_khmer(text: str) -> bool:
    return bool(re.search(r'[\u1780-\u17FF]', text))

def clean_title(title: str) -> str:
    return title.replace("(SPS-TPR)", "").replace("SPS-TPR", "").strip()

def classify_grade(title: str, is_kh: bool):
    t_low = title.lower()
    if is_kh:
        if "មត្តេយ្យ" in title:
            return "មត្តេយ្យ"
        elif any(k in title for k in ["ទី៧", "ទី៨", "ទី៩", "ទី១០", "ទី១១", "ទី១២"]):
            return "មធ្យម"
        else:
            return "បឋម"
    else:
        if any(k in t_low for k in ["k1", "k2", "k3", "nursery", "kindergarten"]):
            return "Kindergarten"
        elif any(f"level {i}" in t_low for i in range(7, 13)):
            return "Secondary"
        else:
            return "Primary"

def generate_report_text():
    conn = sqlite3.connect("tracker.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT group_title, last_active, count_text, count_voice, 
               count_photo, count_video, count_file, count_link, today_messages 
        FROM group_activity
    """)
    rows = cursor.fetchall()
    conn.close()

    now = datetime.now()
    today_date_str = now.strftime('%d/%m/%Y')

    greeting_header = (
        f"🙏 <b>គោរពជម្រាបសួរលោកនាយក</b>\n"
        f"ខ្ញុំបាទសូមគោរពជូនរបាយការណ៍GROUPសិក្សាប្រចាំថ្ងៃ សម្រាប់ថ្ងៃទី <b>{today_date_str}</b> ដូចខាងក្រោម៖\n\n"
        f"🏫 <b>សាខាៈ សុវណ្ណភូមិទួលពង្រ</b>\n"
    )

    if not rows:
        return greeting_header + "⚠️ <i>មិនទាន់មានទិន្នន័យសកម្មភាពក្នុងប្រព័ន្ធនៅឡើយទេ។</i>"

    kh_groups = {"មត្តេយ្យ": [], "បឋម": [], "មធ្យម": []}
    en_groups = {"Kindergarten": [], "Primary": [], "Secondary": []}
    kh_inactive, en_inactive = [], []

    tot_text = tot_voice = tot_photo = tot_video = tot_file = tot_link = 0

    for row in rows:
        title = row[0]
        last_active_str = row[1]
        c_text = row[2] or 0
        c_voice = row[3] or 0
        c_photo = row[4] or 0
        c_video = row[5] or 0
        c_file = row[6] or 0
        c_link = row[7] or 0
        today_m = row[8] or 0

        subtotal = c_text + c_voice + c_photo + c_video + c_file + c_link
        if subtotal == 0 and today_m > 0:
            subtotal = today_m
            c_text = today_m

        tot_text += c_text
        tot_voice += c_voice
        tot_photo += c_photo
        tot_video += c_video
        tot_file += c_file
        tot_link += c_link

        try:
            last_active = datetime.fromisoformat(last_active_str)
            last_active_display = last_active.strftime('%d/%m %H:%M')
        except Exception:
            last_active_display = str(last_active_str)

        cleaned = clean_title(title)
        is_kh = is_khmer(title)
        grade = classify_grade(cleaned, is_kh)

        item_data = {
            "title": cleaned,
            "subtotal": subtotal,
            "text": c_text, "voice": c_voice, "photo": c_photo,
            "video": c_video, "file": c_file, "link": c_link
        }

        if subtotal > 0:
            if is_kh:
                kh_groups[grade].append(item_data)
            else:
                en_groups[grade].append(item_data)
        else:
            inactive_str = f"• {cleaned} <i>(ចុងក្រោយ: {last_active_display})</i>"
            if is_kh:
                kh_inactive.append(inactive_str)
            else:
                en_inactive.append(inactive_str)

    total_all_msg = tot_text + tot_voice + tot_photo + tot_video + tot_file + tot_link

    def summarize_level(items):
        return {
            "classes": len(items),
            "messages": sum(x["subtotal"] for x in items),
            "photos": sum(x["photo"] for x in items),
            "voices": sum(x["voice"] for x in items)
        }

    report = greeting_header
    report += "📊 <b>ស្ថិតិទូទៅប្រចាំថ្ងៃ (DASHBOARD)</b>\n"
    report += "━━━━━━━━━━━━━━━━━━\n"
    report += f"• <b>សារសរុបទាំងអស់:</b> {total_all_msg} សារ\n"
    report += (
        f"  └ 💬Text: {tot_text} | 🎙Voice: {tot_voice} | 🖼Photo: {tot_photo}\n"
        f"  └ 🎬Video: {tot_video} | 📁File: {tot_file} | 🔗Link: {tot_link}\n\n"
    )

    report += "📑 <b>សង្ខេបស្ថិតិតាមកម្រិតសិក្សានីមួយៗ</b>\n"
    report += "─────────────────\n"
    report += "🇰🇭 <u>កម្មវិធីចំណេះទូទៅខ្មែរ:</u>\n"
    for lvl in ["មត្តេយ្យ", "បឋម", "មធ្យម"]:
        s = summarize_level(kh_groups[lvl])
        report += f" • <b>{lvl}:</b> {s['classes']} ថ្នាក់ | {s['messages']} សារ (🖼 {s['photos']} | 🎙 {s['voices']})\n"

    report += "\n🇬🇧 <u>កម្មវិធីភាសាអង់គ្លេសទូទៅ:</u>\n"
    for lvl, name in [("Kindergarten", "មត្តេយ្យ (K)"), ("Primary", "បឋម (L1-6)"), ("Secondary", "មធ្យម (L7-12)")]:
        s = summarize_level(en_groups[lvl])
        report += f" • <b>{name}:</b> {s['classes']} ថ្នាក់ | {s['messages']} សារ (🖼 {s['photos']} | 🎙 {s['voices']})\n"

    report += "━━━━━━━━━━━━━━━━━━\n\n"

    # ១. កម្មវិធីខ្មែរ
    report += "🇰🇭 <b>១. បញ្ជីថ្នាក់លម្អិត - ចំណេះទូទៅខ្មែរ</b>\n"
    for lvl in ["មត្តេយ្យ", "បឋម", "មធ្យម"]:
        if kh_groups[lvl]:
            report += f"\n🔹 <b>កម្រិត{lvl}:</b>\n"
            kh_groups[lvl].sort(key=lambda x: x["subtotal"], reverse=True)
            for x in kh_groups[lvl]:
                report += (
                    f"• <b>{x['title']}</b>: {x['subtotal']} សារ\n"
                    f"  └ 💬:{x['text']} 🎙:{x['voice']} 🖼:{x['photo']} 🎬:{x['video']} 📁:{x['file']} 🔗:{x['link']}\n"
                )
    if kh_inactive:
        report += "\n⚠️ <u>ថ្នាក់អសកម្ម (ថ្ងៃនេះ):</u>\n" + "\n".join(kh_inactive) + "\n"

    report += "\n" + "═" * 22 + "\n\n"

    # ២. កម្មវិធីអង់គ្លេស
    report += "🇬🇧 <b>២. បញ្ជីថ្នាក់លម្អិត - ភាសាអង់គ្លេសទូទៅ</b>\n"
    for lvl, label in [("Kindergarten", "កម្រិត Kindergarten"), ("Primary", "កម្រិត Primary"), ("Secondary", "កម្រិត Secondary")]:
        if en_groups[lvl]:
            report += f"\n🔹 <b>{label}:</b>\n"
            en_groups[lvl].sort(key=lambda x: x["subtotal"], reverse=True)
            for x in en_groups[lvl]:
                report += (
                    f"• <b>{x['title']}</b>: {x['subtotal']} សារ\n"
                    f"  └ 💬:{x['text']} 🎙:{x['voice']} 🖼:{x['photo']} 🎬:{x['video']} 📁:{x['file']} 🔗:{x['link']}\n"
                )
    if en_inactive:
        report += "\n⚠️ <u>ថ្នាក់អសកម្ម (ថ្ងៃនេះ):</u>\n" + "\n".join(en_inactive) + "\n"

    return report

# Function ពុះសារវែងៗកុំឱ្យ Error 4096 Limit
async def send_safely(chat_id, text):
    if len(text) <= 4000:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    else:
        parts = text.split("══════════════════════")
        for part in parts:
            if part.strip():
                await bot.send_message(chat_id=chat_id, text=part.strip(), parse_mode="HTML")
                await asyncio.sleep(0.5)

# Function ផ្ញើរបាយការណ៍ស្វ័យប្រវត្តិតាមពេលកំណត់
async def send_daily_report():
    if ADMIN_CHAT_ID:
        report = generate_report_text()
        await send_safely(ADMIN_CHAT_ID, report)
        
        # Reset ការរាប់ប្រចាំថ្ងៃ
        conn = sqlite3.connect("tracker.db")
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE group_activity 
            SET today_messages = 0, today_photos = 0,
                count_text = 0, count_voice = 0, count_photo = 0, 
                count_video = 0, count_file = 0, count_link = 0
        """)
        conn.commit()
        conn.close()

# Commands សម្រាប់ Admin
@dp.message(Command("report"))
async def manual_report(message: types.Message):
    try:
        report = generate_report_text()
        await send_safely(message.chat.id, report)
    except Exception as e:
        await message.answer(f"⚠️ កើតមានបញ្ហា៖ {str(e)}")

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer("គោរពជម្រាបសួរលោកនាយក! Bot តាមដានសកម្មភាពថ្នាក់រៀនកំពុងដំណើរការធម្មតា។ វាយ /report ដើម្បីពិនិត្យរបាយការណ៍។")

async def main():
    init_db()
    # កំណត់ផ្ញើស្វ័យប្រវត្តិម៉ោង ១០:០០ យប់ (ម៉ោងនៅភ្នំពេញ)
    scheduler.add_job(send_daily_report, 'cron', hour=22, minute=0, timezone='Asia/Phnom_Penh')
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
