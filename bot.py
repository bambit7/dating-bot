import sqlite3

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, ContextTypes, filters

from config import BOT_TOKEN, ADMIN_ID, CONTACT_PRICE, CARD_NUMBER, CLICK_PHONE

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
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO girls (telegram_id, name, age, region, bio, contact, photo, approved)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    """, (telegram_id, name, age, region, bio, contact, photo))
    conn.commit()
    conn.close()

def get_girls_by_region(region):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, age, region, bio, photo
        FROM girls
        WHERE region=? AND approved=1
    """, (region,))
    data = cur.fetchall()
    conn.close()
    return data

def get_girl_contact(girl_id):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT name, contact FROM girls WHERE id=?", (girl_id,))
    data = cur.fetchone()
    conn.close()
    return data

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Kim sifatida kirmoqchisiz?",
        reply_markup=ReplyKeyboardMarkup([["👦 O‘g‘il", "👧 Qiz"]], resize_keyboard=True)
    )
    return GENDER

async def gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["gender"] = update.message.text
    await update.message.reply_text(
        "Viloyatingizni tanlang:",
        reply_markup=ReplyKeyboardMarkup(regions, resize_keyboard=True)
    )
    return REGION

async def region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["region"] = update.message.text

    if context.user_data["gender"] == "👧 Qiz":
        await update.message.reply_text("Rasmingizni yuboring 📸", reply_markup=ReplyKeyboardRemove())
        return PHOTO

    girls = get_girls_by_region(context.user_data["region"])

    if not girls:
        await update.message.reply_text("Bu viloyatda hozircha qizlar yo‘q.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    girl_id, name, age, girl_region, bio, photo = girls[0]

    keyboard = [
        [InlineKeyboardButton(f"💳 Kontaktni ochish — {CONTACT_PRICE} so‘m", callback_data=f"buy_{girl_id}")],
        [InlineKeyboardButton("➡️ Keyingisi", callback_data=f"next_{girl_region}_0")]
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
        reply_markup=InlineKeyboardMarkup(keyboard)
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
    user = update.effective_user
    context.user_data["contact"] = update.message.text

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
        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{user.id}")
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
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text("✅ Profilingiz adminga yuborildi.")
    return ConversationHandler.END

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("approve_"):
        user_id = data.split("_")[1]
        profile = context.bot_data.get(user_id)

        if not profile:
            await query.edit_message_caption(caption="❌ Profil topilmadi.")
            return

        save_girl(**profile)

        await query.edit_message_caption(caption="✅ Profil tasdiqlandi va bazaga qo‘shildi.")
        await context.bot.send_message(profile["telegram_id"], "✅ Profilingiz tasdiqlandi!")

    elif data.startswith("reject_"):
        user_id = data.split("_")[1]
        profile = context.bot_data.get(user_id)

        await query.edit_message_caption(caption="❌ Profil rad etildi.")

        if profile:
            await context.bot.send_message(profile["telegram_id"], "❌ Profilingiz rad etildi.")

    elif data.startswith("buy_"):
        girl_id = data.split("_")[1]
        context.user_data["paying_girl_id"] = girl_id

        await query.message.reply_text(
            f"💳 Click orqali to‘lov\n\n"
            f"Summa: {CONTACT_PRICE} so‘m\n"
            f"Karta: {CARD_NUMBER}\n"
            f"Click telefon: {CLICK_PHONE}\n\n"
            "To‘lov qilgandan keyin chek screenshotini shu yerga yuboring 📸"
        )

    elif data.startswith("payok_"):
        _, user_id, girl_id = data.split("_")
        girl = get_girl_contact(girl_id)

        if not girl:
            await query.message.reply_text("❌ Kontakt topilmadi.")
            return

        name, contact_info = girl

        await context.bot.send_message(
            chat_id=int(user_id),
            text=f"✅ To‘lov tasdiqlandi!\n\n👧 {name}\n📞 Kontakt: {contact_info}"
        )

        await query.edit_message_caption(caption="✅ To‘lov tasdiqlandi. Kontakt yuborildi.")

    elif data.startswith("payno_"):
        _, user_id, girl_id = data.split("_")

        await context.bot.send_message(
            chat_id=int(user_id),
            text="❌ To‘lov rad etildi. Iltimos, to‘g‘ri chek yuboring."
        )

        await query.edit_message_caption(caption="❌ To‘lov rad etildi.")

    elif data.startswith("next_"):
        parts = data.split("_")
        region_name = parts[1]
        index = int(parts[2]) + 1

        girls = get_girls_by_region(region_name)

        if index >= len(girls):
            await query.message.reply_text("Bu viloyatda boshqa profil yo‘q.")
            return

        girl_id, name, age, girl_region, bio, photo = girls[index]

        keyboard = [
            [InlineKeyboardButton(f"💳 Kontaktni ochish — {CONTACT_PRICE} so‘m", callback_data=f"buy_{girl_id}")],
            [InlineKeyboardButton("➡️ Keyingisi", callback_data=f"next_{girl_region}_{index}")]
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
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def payment_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    girl_id = context.user_data.get("paying_girl_id")

    if not girl_id:
        return

    user = update.effective_user
    photo_id = update.message.photo[-1].file_id

    keyboard = [[
        InlineKeyboardButton("✅ To‘lovni tasdiqlash", callback_data=f"payok_{user.id}_{girl_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"payno_{user.id}_{girl_id}")
    ]]

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=(
            "💳 Yangi to‘lov cheki\n\n"
            f"👤 User: {user.first_name}\n"
            f"🆔 ID: {user.id}\n"
            f"👧 Profil ID: {girl_id}\n"
            f"💰 Summa: {CONTACT_PRICE} so‘m"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text("✅ Chek adminga yuborildi. Tasdiqlanishini kuting.")

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
app.add_handler(MessageHandler(filters.PHOTO, payment_screenshot))

print("Bot ishga tushdi...")
app.run_polling()