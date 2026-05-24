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

cancel_keyboard = ReplyKeyboardMarkup([["❌ Bekor qilish"]], resize_keyboard=True)


def db():
    return sqlite3.connect("users.db")


def get_existing_profile(telegram_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM girls WHERE telegram_id=?", (telegram_id,))
    data = cur.fetchone()
    conn.close()
    return data


def save_or_update_girl(telegram_id, name, age, region, bio, contact, photo):
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM girls WHERE telegram_id=?", (telegram_id,))
    old = cur.fetchone()

    if old:
        cur.execute("""
            UPDATE girls
            SET name=?, age=?, region=?, bio=?, contact=?, photo=?, approved=1
            WHERE telegram_id=?
        """, (name, age, region, bio, contact, photo, telegram_id))
    else:
        cur.execute("""
            INSERT INTO girls (telegram_id, name, age, region, bio, contact, photo, approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (telegram_id, name, age, region, bio, contact, photo))

    conn.commit()
    conn.close()


def get_girls_by_region(region):
    conn = db()
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
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT name, contact FROM girls WHERE id=?", (girl_id,))
    data = cur.fetchone()
    conn.close()
    return data


def get_stats():
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM girls")
    girls_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM purchases")
    payments_count = cur.fetchone()[0]

    conn.close()
    return girls_count, payments_count, payments_count * CONTACT_PRICE


def profile_caption(name, age, region, bio):
    return (
        "✨ <b>QIZ PROFILI</b> ✨\n\n"
        f"👤 <b>Ism:</b> {name}\n"
        f"🎂 <b>Yosh:</b> {age}+\n"
        f"📍 <b>Viloyat:</b> {region}\n"
        f"💬 <b>Bio:</b> {bio}\n\n"
        "🔐 <b>Kontakt:</b> Yashirin\n"
        "💳 Kontaktni ochish uchun to‘lov qiling"
    )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    girls_count, payments_count, total_money = get_stats()

    await update.message.reply_text(
        "📊 <b>ADMIN STATISTIKA</b>\n\n"
        f"👧 Qiz profillari: <b>{girls_count}</b>\n"
        f"💳 Tasdiqlangan to‘lovlar: <b>{payments_count}</b>\n"
        f"💰 Tushum: <b>{total_money} so‘m</b>",
        parse_mode="HTML"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "🔥 <b>Real tanishuv botiga xush kelibsiz!</b>\n\n"
        "Kim sifatida kirmoqchisiz?",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            [["👦 O‘g‘il", "👧 Qiz"]],
            resize_keyboard=True
        )
    )
    return GENDER


async def gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, context)

    context.user_data["gender"] = update.message.text

    await update.message.reply_text(
        "📍 Viloyatingizni tanlang:",
        reply_markup=ReplyKeyboardMarkup(regions + [["❌ Bekor qilish"]], resize_keyboard=True)
    )
    return REGION


async def region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Bekor qilish":
        return await cancel(update, context)

    context.user_data["region"] = update.message.text

    if context.user_data["gender"] == "👧 Qiz":
        existing = get_existing_profile(update.effective_user.id)

        if existing:
            await update.message.reply_text(
                "ℹ️ Sizda oldin profil bor.\n\n"
                "Yangi ma’lumot yuborsangiz, eski profilingiz admin tasdig‘idan keyin yangilanadi."
            )

        await update.message.reply_text(
            "📸 Rasmingizni yuboring\n\n"
            "⚠️ Faqat o‘zingizga tegishli rasm yuboring.",
            reply_markup=cancel_keyboard
        )
        return PHOTO

    girls = get_girls_by_region(context.user_data["region"])

    if not girls:
        await update.message.reply_text(
            "😕 Bu viloyatda hozircha qizlar yo‘q.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    girl_id, name, age, girl_region, bio, photo = girls[0]

    keyboard = [
        [InlineKeyboardButton(f"💳 Kontaktni ochish — {CONTACT_PRICE} so‘m", callback_data=f"buy_{girl_id}")],
        [InlineKeyboardButton("➡️ Keyingisi", callback_data=f"next_{girl_region}_0")]
    ]

    await update.message.reply_photo(
        photo=photo,
        caption=profile_caption(name, age, girl_region, bio),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["photo"] = update.message.photo[-1].file_id

    await update.message.reply_text(
        "📝 O‘zingiz haqingizda qisqa bio yozing.\n\n"
        "Masalan: Salom, tanishishga ochiqman.",
        reply_markup=cancel_keyboard
    )
    return BIO


async def bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(update.message.text) < 5:
        await update.message.reply_text("Bio juda qisqa. Kamida 5 ta belgi yozing.")
        return BIO

    context.user_data["bio"] = update.message.text

    await update.message.reply_text(
        "📞 Telegram username yoki telefon raqamingizni yuboring.\n\n"
        "Masalan:\n@username\n+998901234567",
        reply_markup=cancel_keyboard
    )
    return CONTACT


async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact_text = update.message.text.strip()

    if len(contact_text) < 5:
        await update.message.reply_text("Kontakt noto‘g‘ri. Qayta yuboring.")
        return CONTACT

    user = update.effective_user

    context.bot_data[str(user.id)] = {
        "telegram_id": user.id,
        "name": user.first_name,
        "age": 18,
        "region": context.user_data["region"],
        "bio": context.user_data["bio"],
        "contact": contact_text,
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
            "🆕 <b>YANGI / YANGILANGAN PROFIL</b>\n\n"
            f"👤 Ism: {user.first_name}\n"
            f"📍 Viloyat: {context.user_data['region']}\n"
            f"💬 Bio: {context.user_data['bio']}\n"
            f"📞 Kontakt: {contact_text}\n"
            f"🆔 ID: {user.id}"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text(
        "✅ Profilingiz adminga yuborildi.\n\n"
        "Tasdiqlangandan keyin botda ko‘rinadi.",
        reply_markup=ReplyKeyboardRemove()
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
            await query.edit_message_caption(caption="❌ Profil topilmadi. Qiz qayta yuborsin.")
            return

        save_or_update_girl(**profile)

        await query.edit_message_caption(caption="✅ Profil tasdiqlandi va bazaga saqlandi.")
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
            "💳 <b>Click orqali to‘lov</b>\n\n"
            f"💰 Summa: <b>{CONTACT_PRICE} so‘m</b>\n"
            f"💳 Karta: <code>{CARD_NUMBER}</code>\n"
            f"📱 Click telefon: <code>{CLICK_PHONE}</code>\n\n"
            "To‘lov qilgandan keyin chek screenshotini yuboring 📸",
            parse_mode="HTML",
            reply_markup=cancel_keyboard
        )

    elif data.startswith("payok_"):
        _, user_id, girl_id = data.split("_")
        girl = get_girl_contact(girl_id)

        if not girl:
            return

        name, contact_info = girl

        conn = db()
        cur = conn.cursor()
        cur.execute("INSERT INTO purchases (boy_id, girl_id) VALUES (?, ?)", (user_id, girl_id))
        conn.commit()
        conn.close()

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
            caption=profile_caption(name, age, girl_region, bio),
            parse_mode="HTML",
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
            "💳 <b>YANGI TO‘LOV CHEKI</b>\n\n"
            f"👤 User: {user.first_name}\n"
            f"🆔 ID: {user.id}\n"
            f"👧 Profil ID: {girl_id}\n"
            f"💰 Summa: {CONTACT_PRICE} so‘m"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    await update.message.reply_text(
        "✅ Chek adminga yuborildi. Tasdiqlanishini kuting.",
        reply_markup=ReplyKeyboardRemove()
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "❌ Amal bekor qilindi.\n\nQayta boshlash uchun /start bosing.",
        reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END


app = Application.builder().token(BOT_TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender)],
        REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, region)],
        PHOTO: [
            MessageHandler(filters.TEXT & filters.Regex("❌ Bekor qilish"), cancel),
            MessageHandler(filters.PHOTO, photo),
        ],
        BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, bio)],
        CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact)],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        MessageHandler(filters.TEXT & filters.Regex("❌ Bekor qilish"), cancel)
    ],
)

app.add_handler(conv_handler)
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.PHOTO, payment_screenshot))
app.add_handler(CommandHandler("admin", admin_panel))
app.add_handler(MessageHandler(filters.TEXT & filters.Regex("❌ Bekor qilish"), cancel))

print("Bot ishga tushdi...")
app.run_polling()