import logging
import json
import os
import math
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from google.oauth2 import service_account

creds = service_account.Credentials.from_service_account_file("sheets.json")


# --- Configuration ---
BOT_TOKEN = "8139591798:AAGVOiWU4kaznZsladthZ1DXoh4gHid3kLU"
JSON_FILE_PATH = 'sheets.json'

SUBJECT_ORDER = [
    "English", "Mathematics", "Biology", "Physics",
    "Chemistry", "Geography", "History", "Economics", "SAT"
]

MAX_SCORES = {
    "English": 100,
    "Mathematics": 65,
    "Biology": 100,
    "Physics": 60,
    "Chemistry": 80,
    "Geography": 100,
    "History": 100,
    "Economics": 80,
    "SAT": 60
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ASKING_PHONE = range(1)

def load_results_data(file_path: str) -> list | None:
    if not os.path.exists(file_path):
        logger.error(f"Error: JSON file not found at {file_path}")
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.error(f"Error: JSON data in {file_path} is not a list.")
            return None
        return data
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON from {file_path}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred loading {file_path}: {e}")
        return None

def find_student_records(phone_number: str, data: list) -> list:
    found_records = []
    if not data:
        return []
    search_phone = phone_number.strip()
    for record in data:
        if record.get("Phone_number") and record["Phone_number"].strip() == search_phone:
            found_records.append(record)
    return found_records

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "ሰላም! የፈተናዎን ውጤት ለማየት ስልክ ቁጥርዎን ያስገቡ።\n"
    )
    return ASKING_PHONE

async def received_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone_number = update.message.text.strip()
    user = update.message.from_user
    logger.info(f"User {user.first_name} ({user.id}) entered phone number: {phone_number}")

    student_data = load_results_data(JSON_FILE_PATH)

    if student_data is None:
        await update.message.reply_text(
            "እባኮትን ድጋሚ ይሞክሩ"
        )
        return ConversationHandler.END

    student_records = find_student_records(phone_number, student_data)

    if not student_records:
        await update.message.reply_text(
            f"ይቅርታ፣ በዚህ ስልክ ቁጥር {phone_number} የተመዘገበ ውጤት አልተገኘም።\n"
            "እባክዎ ቁጥሩን ድጋሚ ያረጋግጡ አና ይላኩ።"
        )
    else:
        scores_by_subject = {}
        student_name = student_records[0].get("Name", "N/A")

        for record in student_records:
            subject = record.get("subject")
            score = record.get("exam_score")
            if subject and score is not None:
                try:
                    scores_by_subject[subject.strip()] = float(score)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid score format '{score}' for subject '{subject}' and phone '{phone_number}'.")

        response_message = "━━━━━━📚 ውጤት 📚━━━━━━\n"
        response_message += f"📋የተማሪ ስም: {student_name} (ስልክ: {phone_number})\n"
        response_message += "--------------------\n"

        total_actual_score = 0.0
        total_maximum_score = 0.0
        total_percentage_sum = 0.0
        subject_count = 0
        found_any_results = False

        for subject in SUBJECT_ORDER:
            if subject in scores_by_subject:
                actual_score = scores_by_subject[subject]
                maximum_score = MAX_SCORES.get(subject)

                score_display = ""
                percentage = None
                if maximum_score is not None:
                    if maximum_score > 0:
                        percentage = (actual_score / maximum_score) * 100
                        score_display = f"{int(actual_score) if actual_score == int(actual_score) else actual_score}/{int(maximum_score)}  ({percentage:.1f}%)"

                        total_actual_score += actual_score
                        total_maximum_score += maximum_score
                        total_percentage_sum += percentage
                        subject_count += 1
                    else:
                        score_display = f"{actual_score}/0 (ስህተት: ከፍተኛ ውጤት 0 ነው)"
                else:
                    score_display = f"{actual_score} (ከፍተኛ ውጤት ያልተቀመጠ)"

                response_message += f"📚የትምህርት አይነት: {subject}\n 📊ውጤት: {score_display}\n"
                response_message += "--------------------\n"
                found_any_results = True

        average_percentage = 0.0
        feedback_message = "ምንም አይነት አስተያየት ማቅረብ አልተቻለም።"
        summary_block = ""

        if subject_count > 0 and total_maximum_score > 0:
            average_percentage = (total_actual_score / total_maximum_score) * 100

            if average_percentage >= 85:
                feedback_message = "🌟 እጅግ አስደናቂ ውጤት! በዚህ ውጤት የመጀመሪያ ምርጫ የሆነው ዩኒቨርሲቲ መግባት ይችላሉ።"
            elif average_percentage >= 75:
                feedback_message = "👍 በጣም ጥሩ ውጤት! የመጀመሪያ ወይም የሁለተኛ ምርጫ የሆነው ዩኒቨርሲቲ መግባት ይችላሉ።"
            elif average_percentage >= 70:
                feedback_message = "✅ ጥሩ ውጤት! ከመጀመሪያ እስከ አምስተኛ ምርጫ ላይ ያሉ ዩኒቨርሲቲዎች ውስጥ መግባት ይችላሉ።"
            elif average_percentage >= 60:
                feedback_message = "🤔 የበለጠ ሥራና ልምምድ ያስፈልጋል። እባክዎ ወደ ፈለጉት ዩኒቨርሲቲ ለመግባት ጠንክረው ይለማመዱ።"
            elif average_percentage >= 50:
                feedback_message = "⚠️ የማለፍ እና የመውደቅ እድልዎ 50/50 ነው። ስለማለፍዎ እርግጠኛ ለመሆን ተጨማሪ ልምምድ ያድርጉ።"
            else:
                feedback_message = "📉 አልተሳካም፣ ነገር ግን በትክክለኛ ክለሳ አና ጥያቄዎች በኋል ማለፍ ይቻላል በርታ/በርቺ።"

            rounded_percentage_sum = math.ceil(total_percentage_sum)
            max_percentage_total = subject_count * 100

            summary_block += "```\n"
            summary_block += f"🏆የጠቅላላ ውጤት: {rounded_percentage_sum} / {max_percentage_total} (ከ{subject_count} ትምህርት)\n"
            summary_block += f"📊አማካይ ውጤት:          {average_percentage:.1f}%\n\n"
            summary_block += f"{feedback_message}\n"
            summary_block += "```"

            response_message += f"\n{summary_block}"

        elif found_any_results:
            response_message += "\nበተገኙ ውጤቶች ላይ ያልተሟላ መረጃ ስለነበረ አጠቃላይ ውጤት መቆጣጠር አልተቻለም።"
        else:
            response_message = (
                f"የተማሪ {student_name} ({phone_number}) ለመታየት ውጤት ተገኘ፣ "
                f"ግን በየክፍሉ ውስጥ የሚያሳዩ ውጤቶች አልተገኙም።\n"
                f"እባኮትን ድጋፍ ለማግኘት አግኙ።"
            )

        await update.message.reply_text(response_message, parse_mode='Markdown')

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info(f"User {user.first_name} ({user.id}) canceled the conversation.")
    await update.message.reply_text(
        'እሺ፣ ተቋርጧል።', reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ይቅርታ፣ /start ይሞክሩ።")

def main() -> None:
    try:
        application = Application.builder().token(BOT_TOKEN).build()
    except ValueError as e:
        logger.error(f"Error initializing bot: {e}")
        return

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('results', start)],
        states={ASKING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_phone_number)]},
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Bot stopped.")

if __name__ == '__main__':
    if BOT_TOKEN.startswith("813959"):
        logger.critical("CRITICAL WARNING: Replace this token immediately!")
    main()
