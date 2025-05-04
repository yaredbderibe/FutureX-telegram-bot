import logging
import gspread
import pandas as pd
import asyncio
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Course Configuration
COURSE_SHEETS = {
    "English": {"sheet_name": "English Model Exam I", "max_score": 100},
    "Mathematics": {"sheet_name": "Mathematics Model Exam I", "max_score": 100},
    "Biology": {"sheet_name": "Biology Model Exam I", "max_score": 100},
    "Physics": {"sheet_name": "Physics Model Exam I", "max_score": 100},
    "Chemistry": {"sheet_name": "Chemistry Model Exam I", "max_score": 100},
    "History": {"sheet_name": "History Model Exam I", "max_score": 100},
    "Economics": {"sheet_name": "Economics Model Exam I", "max_score": 100},
    "Geography": {"sheet_name": "Geography Model Exam I", "max_score": 100},
    "SAT": {"sheet_name": "SAT Model Exam I", "max_score": 100}
}

REQUIRED_COLUMNS = ['Name', 'Phone Number', 'Score']

async def delete_message_after_delay(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int = 1):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.warning(f"Could not delete message {message_id}: {e}")

def normalize_score(score_str, max_score):
    try:
        if pd.isna(score_str) or score_str == "":
            return None
        if '/' in str(score_str):
            obtained, total = map(float, str(score_str).split('/'))
            percentage = (obtained / total) * 100
        else:
            percentage = (float(score_str) / max_score) * 100
        return round(percentage, 1)
    except Exception as e:
        logger.error(f"Score normalization failed for '{score_str}': {str(e)}")
        return None

def get_student_data(phone):
    results = {}
    normalized_scores = {}
    total_percentage = 0
    subjects_taken = 0
    name = None
    detailed_errors = []

    for course, config in COURSE_SHEETS.items():
        sheet_name = config["sheet_name"]
        max_score = config["max_score"]

        try:
            try:
                sheet = client.open(sheet_name).sheet1
                data = sheet.get_all_records()
                df = pd.DataFrame(data)
            except gspread.exceptions.SpreadsheetNotFound:
                detailed_errors.append(f"{course}: Spreadsheet not found")
                results[course] = "Sheet not available"
                continue
            except Exception as e:
                detailed_errors.append(f"{course}: Could not access sheet - {str(e)}")
                results[course] = "Data unavailable"
                continue

            missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
            if missing_cols:
                detailed_errors.append(f"{course}: Missing columns - {', '.join(missing_cols)}")
                results[course] = "Incomplete data"
                continue

            df['Phone Number'] = (
                df['Phone Number']
                .astype(str)
                .str.replace(r'\D', '', regex=True)
                .str.lstrip('0')
            )

            student = df[df['Phone Number'] == phone]

            if student.empty:
                results[course] = "Exam not taken"
                continue

            record = student.iloc[0]
            if name is None:
                name = record['Name']

            score_value = record.get('Score')
            normalized = normalize_score(score_value, max_score)

            if normalized is None:
                detailed_errors.append(f"{course}: Could not process score '{score_value}'")
                results[course] = "Invalid score format"
                continue

            results[course] = f"{normalized}%"
            normalized_scores[course] = normalized
            total_percentage += normalized
            subjects_taken += 1

        except Exception as e:
            logger.exception(f"Unexpected error processing {course}")
            detailed_errors.append(f"{course}: Processing error")
            results[course] = "System error"

    return name, results, normalized_scores, total_percentage, subjects_taken, detailed_errors

# ... all imports and configuration remain unchanged ...

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🌿 ናቸራል", callback_data="stream_natural")],
        [InlineKeyboardButton("🌍 ሶሻል", callback_data="stream_social")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "📚 FutureX የሞዴል ፈተና ውጤት\n\n"
        "እባክዎ stream ይምረጡ",
        reply_markup=reply_markup
    )

async def stream_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "stream_natural":
        context.user_data['stream'] = 'natural'
        await query.edit_message_text("✅ የተመረጠው Stream: ናቸራል\n\nአሁን ውጤትዎን ለማየት ስልክ ቁጥርዎን ያስገቡ።")
    elif query.data == "stream_social":
        context.user_data['stream'] = 'social'
        await query.edit_message_text("✅ የተመረጠው Stream: ሶሻል\n\nአሁን ውጤትዎን ለማየት ስልክ ቁጥርዎን ያስገቡ።")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'stream' not in context.user_data:
        await update.message.reply_text("ℹ️ እባክዎ በመጀመሪያ /start በመጠቀም stream ይምረጡ።")
        return

    stream = context.user_data['stream']
    user_input = update.message.text.strip()
    phone = ''.join(filter(str.isdigit, user_input)).lstrip('0')

    if not phone or len(phone) < 7:
        await update.message.reply_text("❌ እባክዎ ትክክለኛ የሆነ ስልክ ቁጥር ያስገቡ (ቢያንስ 7 አሃዞች።)")
        return

    processing_msg = await update.message.reply_text(
        "⏳ እባክዎን 20 ሴኮንድ ይጠብቁ... ውጤቶን እየተረጋገጥን ነው።",
        reply_to_message_id=update.message.message_id
    )

    asyncio.create_task(delete_message_after_delay(context, processing_msg.chat_id, processing_msg.message_id))

    name, results, normalized_scores, total_percentage, subjects_taken, detailed_errors = get_student_data(phone)

    if not name:
        error_message = (
            "❌ ከዚህ ስልክ ቁጥር ጋር የተያያዘ ውጤት አልተገኘም።\n\n"
            "ምክንያቶች ሊሆኑ ሚችሉ ነገሮች:\n"
            "- ቁጥሩ አልተመዘገበም\n"
            "- በቁጥሩ ኣጻጻፍ ውስጥ ስህተት አለ\n"
            "- ውጤቶቹ ገና አልታወቁም"
        )
        if detailed_errors:
            error_message += "\n\nተጨማሪ መረጃ:\n" + "\n".join(f"• {e}" for e in detailed_errors[:3])

        result_msg = await update.message.reply_text(error_message)
        asyncio.create_task(delete_message_after_delay(context, result_msg.chat_id, result_msg.message_id, 60))
        return

    message = "<b>━━━━━━📚 ውጤት 📚━━━━━━</b>\n\n"
    message += f"📋 የተማሪ ስም: <b>{name}</b>\n\n📚 የፈተና ውጤት (ከ100):\n"

    if stream == 'natural':
        courses_to_display = ["English", "Mathematics", "Biology", "Physics", "Chemistry", "SAT"]
    else:
        courses_to_display = ["English", "Mathematics", "History", "Economics", "Geography", "SAT"]

    for course in courses_to_display:
        message += f"- {course}: {results.get(course, 'ውጤት አልተገኘም')}\n"

    if subjects_taken > 0:
        average_percentage = total_percentage / subjects_taken
        message += (
            f"\n<pre>"
            f"🏆 አጠቃላይ ውጤት: {total_percentage:.1f}%  (ከ {subjects_taken} ትምህርቶች)\n"
            f"📊 አማካይ ውጤት : {average_percentage:.1f}%"
            f"</pre>\n"
        )

        if average_percentage >= 83:
            message += "\n🎉 <b>አስደናቂ ውጤት! በዚህ ውጤት በመጀመሪያ ምርጫዎ ወደሆነው ዩኒቨርሲቲ መግባት ይችላሉ!</b>"
        elif average_percentage >= 75:
            message += "\n👍 <b>በጣም ጥሩ ውጤት! በዚህ ውጤት በመጀመሪያ ወይም በሁለተኛ ምርጫ ዩኒቨርሲቲ መግባት ይችላሉ!</b>"
        elif average_percentage >= 65:
            message += "\n👍 <b>ጥሩ ውጤት! በዚህ ውጤት አስከ አምስተኛ ምርጫ ድረስ ባሉት ዩኒቨርሲቲዎች ውስጥ መግባት ይችላሉ!</b>"
        elif average_percentage >= 50:
            message += "\n💪 <b>መካከለኛ ውጤት! የማለፍ እድሎ 50/50 ነው</b>"
        else:
            message += "\n🔍 <b>ዝቅ ያለ ውጤት ነው። ተጨማሪ ልምምድ ያስፈልጋል። በርታ/በርቺ ፥ ትችላለህ</b>"
    else:
        message += "\nℹ️ የዚህ ተማሪ ውጤቶች አልተገኙም።"

    await update.message.reply_text(message, parse_mode=ParseMode.HTML)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    await update.message.reply_text(
        "⚠️ ያልተጠበቀ ስህተት ተከስቷል። እባክዎ አንድ ጊዜ ተመልሰው ይሞክሩ።"
    )

def main():
    import os
    application = ApplicationBuilder().token(os.getenv("8139591798:AAGVOiWU4kaznZsladthZ1DXoh4gHid3kLU")).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(stream_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("🤖 Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()

    