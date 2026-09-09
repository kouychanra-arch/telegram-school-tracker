def generate_report_text():
    conn = sqlite3.connect("tracker.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT group_title, last_active, count_text, count_voice, 
               count_photo, count_video, count_file, count_link 
        FROM group_detailed_activity
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

    # Container សម្រាប់បែងចែកទិន្នន័យ
    # កម្រិតខ្មែរ: មត្តេយ្យ, បឋម, អនុវិទ្យាល័យ/វិទ្យាល័យ
    kh_groups = {"មត្តេយ្យ": [], "បឋម": [], "មធ្យម": []}
    # កម្រិតអង់គ្លេស: Nursery/Kindergarten (K), Primary (Level 1-6), Secondary (Level 7-12)
    en_groups = {"Kindergarten": [], "Primary": [], "Secondary": []}

    kh_inactive = []
    en_inactive = []

    # Function សម្គាល់កម្រិតថ្នាក់
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

    tot_text = tot_voice = tot_photo = tot_video = tot_file = tot_link = 0

    for title, last_active_str, c_text, c_voice, c_photo, c_video, c_file, c_link in rows:
        subtotal = c_text + c_voice + c_photo + c_video + c_file + c_link
        tot_text += c_text
        tot_voice += c_voice
        tot_photo += c_photo
        tot_video += c_video
        tot_file += c_file
        tot_link += c_link

        last_active = datetime.fromisoformat(last_active_str)
        cleaned = clean_title(title)
        is_kh = is_khmer(title)
        grade = classify_grade(cleaned, is_kh)

        item_data = {
            "title": cleaned,
            "subtotal": subtotal,
            "text": c_text, "voice": c_voice, "photo": c_photo,
            "video": c_video, "file": c_file, "link": c_link,
            "last_active": last_active
        }

        if subtotal > 0:
            if is_kh:
                kh_groups[grade].append(item_data)
            else:
                en_groups[grade].append(item_data)
        else:
            inactive_str = f"• {cleaned} <i>(ចុងក្រោយ: {last_active.strftime('%d/%m %H:%M')})</i>"
            if is_kh:
                kh_inactive.append(inactive_str)
            else:
                en_inactive.append(inactive_str)

    total_all_msg = tot_text + tot_voice + tot_photo + tot_video + tot_file + tot_link

    # Helper គណនាសរុបតាម Level
    def summarize_level(items):
        return {
            "active_classes": len(items),
            "messages": sum(x["subtotal"] for x in items),
            "photos": sum(x["photo"] for x in items),
            "voices": sum(x["voice"] for x in items)
        }

    # Dashboard សង្ខេបជារួម
    report = greeting_header
    report += "📊 <b>ស្ថិតិទូទៅប្រចាំថ្ងៃ (DASHBOARD)</b>\n"
    report += "━━━━━━━━━━━━━━━━━━\n"
    report += f"• <b>សារសរុបទាំងអស់:</b> {total_all_msg} សារ\n"
    report += (
        f"  └ 💬Text: {tot_text} | 🎙Voice: {tot_voice} | 🖼Photo: {tot_photo}\n"
        f"  └ 🎬Video: {tot_video} | 📁File: {tot_file} | 🔗Link: {tot_link}\n\n"
    )

    # តារាងសង្ខេបតាមកម្រិតសិក្សា
    report += "📑 <b>សង្ខេបស្ថិតិតាមកម្រិតសិក្សានីមួយៗ</b>\n"
    report += "─────────────────\n"
    
    # សង្ខេបខ្មែរ
    report += "🇰🇭 <u>កម្មវិធីចំណេះទូទៅខ្មែរ:</u>\n"
    for lvl in ["មត្តេយ្យ", "បឋម", "មធ្យម"]:
        s = summarize_level(kh_groups[lvl])
        report += f" • <b>{lvl}:</b> {s['active_classes']} ថ្នាក់សកម្ម | {s['messages']} សារ (🖼 {s['photos']} | 🎙 {s['voices']})\n"

    # សង្ខេបអង់គ្លេស
    report += "\n🇬🇧 <u>កម្មវិធីភាសាអង់គ្លេសទូទៅ:</u>\n"
    for lvl, name in [("Kindergarten", "ថ្នាក់ K (មត្តេយ្យ)"), ("Primary", "កម្រិតបឋម (L1-6)"), ("Secondary", "កម្រិតមធ្យម (L7-12)")]:
        s = summarize_level(en_groups[lvl])
        report += f" • <b>{name}:</b> {s['active_classes']} ថ្នាក់សកម្ម | {s['messages']} សារ (🖼 {s['photos']} | 🎙 {s['voices']})\n"

    report += "━━━━━━━━━━━━━━━━━━\n\n"

    # បង្ហាញបញ្ជីថ្នាក់រៀនលម្អិត
    # ១. កម្មវិធីខ្មែរ
    report += "🇰🇭 <b>១. បញ្ជីថ្នាក់លម្អិត - ចំណេះទូទៅខ្មែរ</b>\n"
    has_kh_active = False
    for lvl in ["មត្តេយ្យ", "បឋម", "មធ្យម"]:
        if kh_groups[lvl]:
            has_kh_active = True
            report += f"\n🔹 <b>កម្រិត{lvl}:</b>\n"
            kh_groups[lvl].sort(key=lambda x: x["subtotal"], reverse=True)
            for x in kh_groups[lvl]:
                report += (
                    f"• <b>{x['title']}</b>: {x['subtotal']} សារ\n"
                    f"  └ 💬:{x['text']} 🎙:{x['voice']} 🖼:{x['photo']} 🎬:{x['video']} 📁:{x['file']} 🔗:{x['link']}\n"
                )
    if not has_kh_active:
        report += "• <i>គ្មានសកម្មភាព</i>\n"

    if kh_inactive:
        report += "\n⚠️ <u>ថ្នាក់អសកម្ម (ថ្ងៃនេះ):</u>\n" + "\n".join(kh_inactive) + "\n"

    report += "\n" + "═" * 22 + "\n\n"

    # ២. កម្មវិធីអង់គ្លេស
    report += "🇬🇧 <b>២. បញ្ជីថ្នាក់លម្អិត - ភាសាអង់គ្លេសទូទៅ</b>\n"
    has_en_active = False
    for lvl, label in [("Kindergarten", "កម្រិត Kindergarten"), ("Primary", "កម្រិត Primary"), ("Secondary", "កម្រិត Secondary")]:
        if en_groups[lvl]:
            has_en_active = True
            report += f"\n🔹 <b>{label}:</b>\n"
            en_groups[lvl].sort(key=lambda x: x["subtotal"], reverse=True)
            for x in en_groups[lvl]:
                report += (
                    f"• <b>{x['title']}</b>: {x['subtotal']} សារ\n"
                    f"  └ 💬:{x['text']} 🎙:{x['voice']} 🖼:{x['photo']} 🎬:{x['video']} 📁:{x['file']} 🔗:{x['link']}\n"
                )
    if not has_en_active:
        report += "• <i>គ្មានសកម្មភាព</i>\n"

    if en_inactive:
        report += "\n⚠️ <u>ថ្នាក់អសកម្ម (ថ្ងៃនេះ):</u>\n" + "\n".join(en_inactive) + "\n"

    return report
