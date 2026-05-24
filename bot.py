import sqlite3

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, ContextTypes, filters

from config import BOT_TOKEN, ADMIN_ID, CONTACT_PRICE

GENDER, REGION, PHOTO, BIO, CONTACT = range(5)

regions = [
    ["Toshkent", "Samarqand"],
    ["Andijon", "Farg‘ona"],
    ["Namangan", "Buxoro"],
    ["Xorazm", "Qashqadaryo"],
    ["Surxondaryo", "Navoiy"],
]


def save_girl(telegram_id, name, age, region, bio, contact, photo):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO girls (telegram_id, name, age, region, bio, contact, photo, approved)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (telegram_id, name, age, region, bio, contact, photo, 1))
    conn.commit()
    conn.close()


def get_girls_by_region(region):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, age, region, bio, photo
        FROM girls
        WHERE region = ? AND approved = 1
    """, (region,))
    girls = cursor.fetchall()
    conn.close()
    return girls


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["👦 O‘g‘il", "👧 Qiz"]]
    await update.message.reply_text(
        "Kim sifatida kirmoqchisiz?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return GENDER


async def gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gender"] = update.message.text

    await update.message.reply_text(
        "Viloyatingizni tanlang:",
        reply_markup=ReplyKeyboardMarkup(regions, resize_keyboard=True),
    )
    return REGION


async def region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["region"] = update.message.text
    gender_value = context.user_data["gender"]

    if gender_value == "👧 Qiz":
        await update.message.reply_text(
            "Rasmingizni yuboring 📸",
            reply_markup=ReplyKeyboardRemove(),
        )
        return PHOTO

    girls = get_girls_by_region(context.user_data["region"])

    if not girls:
        await update.message.reply_text(
            "Bu viloyatda hozircha qizlar yo‘q.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    girl = girls[0]
    girl_id, name, age, girl_region, bio, photo = girl

    keyboard = [
        [InlineKeyboardButton(f"💳 Kontaktni ochish — {CONTACT_PRICE} so‘m", callback_data=f"buy_{girl_id}")],
        [InlineKeyboardButton("➡️ Keyingisi", callback_data=f"next_{girl_region}_0")],
    ]

    await update.message.reply_photo(
        photo=photo,
        caption=(
            "👧 Qiz profili\n\n"
            f"👤 Ism: {name}\n"
            f"🎂 Yosh: {age}+\n"
            f"🌍 Viloyat: {girl_region}\n"
            f"📝 Bio: {bio}\n\n"
            "📞 Kontakt: 🔒 Yashirin"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return ConversationHandler.END


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["photo"] = update.message.photo[-1].file_id
    await update.message.reply_text("O‘zingiz haqingizda bio yozing 📝")
    return BIO


async def bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bio"] = update.message.text
    await update.message.reply_text("Telegram username yoki telefon raqamingizni yuboring 📞")
    return CONTACT


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["contact"] = update.message.text
    user = update.effective_user

    context.bot_data[str(user.id)] = {
        "telegram_id": user.id,
        "name": user.first_name,
        "age": 18,
        "region": context.user_data["region"],
        "bio": context.user_data["bio"],
        "contact": context.user_data["contact"],
        "photo": context.user_data["photo"],
    }

    keyboard = [[
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{user.id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{user.id}"),
    ]]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=context.user_data["photo"],
        caption=(
            "🆕 Yangi qiz profili\n\n"
            f"👤 Ism: {user.first_name}\n"
            f"🌍 Viloyat: {context.user_data['region']}\n"
            f"📝 Bio: {context.user_data['bio']}\n"
            f"📞 Kontakt: {context.user_data['contact']}\n"
            f"🆔 ID: {user.id}"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    await update.message.reply_text(
        "✅ Profilingiz adminga yuborildi.\nTasdiqlangandan keyin botga joylanadi 🔥"
    )

    return ConversationHandler.END


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("approve_"):
        user_id = data.split("_")[1]
        profile = context.bot_data.get(user_id)

        if not profile:
            await query.edit_message_caption("❌ Profil topilmadi.")
            return

        save_girl(**profile)

        await query.edit_message_caption(
            caption="✅ Profil tasdiqlandi va bazaga qo‘shildi."
        )

        await context.bot.send_message(
            chat_id=profile["telegram_id"],
            text="✅ Profilingiz tasdiqlandi! Endi botda ko‘rinadi 🔥",
        )

    elif data.startswith("reject_"):
        user_id = data.split("_")[1]
        profile = context.bot_data.get(user_id)

        await query.edit_message_caption(caption="❌ Profil rad etildi.")

        if profile:
            await context.bot.send_message(
                chat_id=profile["telegram_id"],
                text="❌ Profilingiz admin tomonidan rad etildi.",
            )

    elif data.startswith("buy_"):
        girl_id = data.split("_")[1]

        await query.message.reply_text(
            f"💳 Kontaktni ochish narxi: {CONTACT_PRICE} so‘m\n\n"
            "Hozircha test rejim.\n"
            "Keyingi bosqichda Click/Payme yoki karta orqali to‘lov ulaymiz."
        )

    elif data.startswith("next_"):
        parts = data.split("_")
        region_name = parts[1]
        index = int(parts[2]) + 1

        girls = get_girls_by_region(region_name)

        if index >= len(girls):
            await query.message.reply_text("Bu viloyatda boshqa profil yo‘q.")
            return

        girl = girls[index]
        girl_id, name, age, girl_region, bio, photo = girl

        keyboard = [
            [InlineKeyboardButton(f"💳 Kontaktni ochish — {CONTACT_PRICE} so‘m", callback_data=f"buy_{girl_id}")],
            [InlineKeyboardButton("➡️ Keyingisi", callback_data=f"next_{girl_region}_{index}")],
        ]

        await query.message.reply_photo(
            photo=photo,
            caption=(
                "👧 Qiz profili\n\n"
                f"👤 Ism: {name}\n"
                f"🎂 Yosh: {age}+\n"
                f"🌍 Viloyat: {girl_region}\n"
                f"📝 Bio: {bio}\n\n"
                "📞 Kontakt: 🔒 Yashirin"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


app = Application.builder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender)],
        REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, region)],
        PHOTO: [MessageHandler(filters.PHOTO, photo)],
        BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, bio)],
        CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

app.add_handler(conv_handler)
app.add_handler(CallbackQueryHandler(buttons))

print("Bot ishga tushdi...")
app.run_polling()