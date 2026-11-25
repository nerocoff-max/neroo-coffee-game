
import os
import sqlite3
import random
import logging
from datetime import date

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

TOKEN = os.getenv("BOT_TOKEN")
DB = "neroo_game.db"
MAX_PRIZES = 5

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TEXT = {
    "uz": {
        "welcome": "☕ Neroo Coffee'га хуш келибсиз!\n\n6 та стакандан бирини танланг. Совғани топсангиз, бепул кофе ютиб оласиз! 🎁",
        "play": "🎮 Ўйинни бошлаш",
        "tries": "🎯 Қолган уринишлар: ",
        "win": "🎉 Табриклаймиз! Сиз бепул кофе ютиб олдингиз! ☕",
        "lose": "😔 Афсус, бу сафар омад кулиб боқмади!",
        "empty": "❌ Бу стакан бўш!",
        "used": "Сиз ўйинда аввал қатнашгансиз. Ҳар бир мижозга фақат бир марта имконият берилади.",
        "limit": "Бугунги 5 та бепул кофе совғаси тугади. Эртага яна омадингизни синаб кўринг!",
        "language": "Тилни танланг / Выберите язык",
        "again": "Ўйин якунланди.",
        "start": "Бошлаш"
    },
    "ru": {
        "welcome": "☕ Добро пожаловать в Neroo Coffee!\n\nВыберите один из 6 стаканов. Найдите подарок и выиграйте бесплатный кофе! 🎁",
        "play": "🎮 Начать игру",
        "tries": "🎯 Осталось попыток: ",
        "win": "🎉 Поздравляем! Вы выиграли бесплатный кофе! ☕",
        "lose": "😔 К сожалению, в этот раз не повезло!",
        "empty": "❌ Этот стакан пуст!",
        "used": "Вы уже участвовали. Каждый клиент может сыграть только один раз.",
        "limit": "Сегодня все 5 бесплатных кофе уже разыграны. Попробуйте завтра!",
        "language": "Выберите язык / Тилни танланг",
        "again": "Игра завершена.",
        "start": "Начать"
    }
}


def db():
    return sqlite3.connect(DB)


def init_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            lang TEXT DEFAULT 'uz'
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS games (
            user_id INTEGER PRIMARY KEY,
            target INTEGER NOT NULL,
            attempts INTEGER DEFAULT 2,
            status TEXT DEFAULT 'active'
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS prizes (
            user_id INTEGER PRIMARY KEY,
            prize_date TEXT NOT NULL
        )
    """)
    con.commit()
    con.close()


def get_lang(user_id):
    con = db()
    row = con.execute(
        "SELECT lang FROM users WHERE user_id=?", (user_id,)
    ).fetchone()
    con.close()
    return row[0] if row else "uz"


def save_lang(user_id, lang):
    con = db()
    con.execute(
        "INSERT OR REPLACE INTO users(user_id,lang) VALUES(?,?)",
        (user_id, lang)
    )
    con.commit()
    con.close()


def keyboard(lang):
    buttons = []
    for i in range(1, 7):
        buttons.append(
            InlineKeyboardButton(
                f"☕ {i}",
                callback_data=f"cup_{i}"
            )
        )
    return InlineKeyboardMarkup([
        buttons[:3],
        buttons[3:]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
        ]
    ])

    await update.message.reply_text(
        "☕ NEROO COFFEE\n\n" + TEXT["uz"]["language"],
        reply_markup=markup
    )


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data.startswith("lang_"):
        lang = data.split("_")[1]
        save_lang(user_id, lang)

        await query.edit_message_text(
            TEXT[lang]["welcome"],
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    TEXT[lang]["play"],
                    callback_data="play"
                )
            ]])
        )
        return

    lang = get_lang(user_id)
    t = TEXT[lang]

    if data == "play":
        con = db()
        old = con.execute(
            "SELECT status FROM games WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if old:
            con.close()
            await query.edit_message_text(t["used"])
            return

        target = random.randint(1, 6)
        con.execute(
            "INSERT INTO games(user_id,target) VALUES(?,?)",
            (user_id, target)
        )
        con.commit()
        con.close()

        await query.edit_message_text(
            t["welcome"] + "\n\n" + t["tries"] + "2",
            reply_markup=keyboard(lang)
        )
        return

    if data.startswith("cup_"):
        cup = int(data.split("_")[1])
        con = db()

        game = con.execute(
            "SELECT target,attempts,status FROM games WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if not game or game[2] != "active":
            con.close()
            await query.edit_message_text(t["again"])
            return

        target, attempts, status = game
        attempts -= 1

        if cup == target:
            today = date.today().isoformat()
            count = con.execute(
                "SELECT COUNT(*) FROM prizes WHERE prize_date=?",
                (today,)
            ).fetchone()[0]

            if count < MAX_PRIZES:
                con.execute(
                    "INSERT INTO prizes(user_id,prize_date) VALUES(?,?)",
                    (user_id, today)
                )
                con.execute(
                    "UPDATE games SET attempts=?,status='won' WHERE user_id=?",
                    (attempts, user_id)
                )
                con.commit()
                con.close()
                await query.edit_message_text(t["win"])
            else:
                con.execute(
                    "UPDATE games SET attempts=?,status='limit' WHERE user_id=?",
                    (attempts, user_id)
                )
                con.commit()
                con.close()
                await query.edit_message_text(t["limit"])
            return

        if attempts <= 0:
            con.execute(
                "UPDATE games SET attempts=0,status='lost' WHERE user_id=?",
                (user_id,)
            )
            con.commit()
            con.close()
            await query.edit_message_text(t["lose"])
            return

        con.execute(
            "UPDATE games SET attempts=? WHERE user_id=?",
            (attempts, user_id)
        )
        con.commit()
        con.close()

        await query.edit_message_text(
            t["empty"] + "\n" + t["tries"] + str(attempts),
            reply_markup=keyboard(lang)
        )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing")

    init_db()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callbacks))

    log.info("Neroo Coffee bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
