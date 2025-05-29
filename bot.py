# -*- coding: utf-8 -*-
"""
Telegram bot: Buy virtual numbers, Telegram Stars & Premium, manage TON balance, and referrals.
© 2025 Barry
"""

import time
import uuid
import threading
import logging
import requests
import binascii

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import pyrebase

from datetime import datetime, timedelta

# === Assets & Constants ===
WELCOME_GIF     = "https://raw.githubusercontent.com/qnexst/404token/main/11.gif"
WALLET_GIF      = "https://raw.githubusercontent.com/qnexst/404token/8f8814776022d61ff67127f7b4bc226499b5a948/wallet.gif"
SERVICE_IMG     = "https://raw.githubusercontent.com/qnexst/404token/main/service.jpg"

BOT_TOKEN       = ""
BOT_USERNAME    = "Arion_Dbot"  # without @
SIM_TOKEN       = ""
CHANNEL_NAME    = "ArionHub"
SUPPORT_USER    = "ArionAdmin"
DEPOSIT_ADDRESS = "UQBRiESLIYaCIL6q9s9frfp3ZGz2Yp29FBycV0GIRZdeY9zP"
TON_API_KEY     = ""
RUN_IN_MAINNET  = True
API_BASE_URL    = "https://toncenter.com" if RUN_IN_MAINNET else "https://testnet.toncenter.com"

# Supported languages
LANGUAGES = {
    "en": "English",
    "ru": "Русский"
}

# === Firebase Real-Time Database Config ===
firebase_config = {
   
}

# === Initialization ===
firebase = pyrebase.initialize_app(firebase_config)
db       = firebase.database()
logging.basicConfig(level=logging.INFO)
bot      = telebot.TeleBot(BOT_TOKEN, parse_mode="MARKDOWN")


# === In-memory Stores ===
pending_topup_memos     = {}  # для /topup: memo -> user_id
last_topup_lts          = {}  # memo -> last lt
pending_discount_memos  = {}  # для скидки: memo -> user_id
last_discount_lts       = {}  # memo -> last lt

NUMBER_SERVICES        = ["telegram","aliexpress","amazon","discord","ebay","facebook","airbnb","tiktok","whatsapp"]
TARIFFS                = [50,100,500,1000,2500,5000]
STAR_PRICES            = {50:0.323,100:0.611,500:2.999,1000:5.899,2500:14,5000:28}
star_selection         = {}
pending_star_orders    = {}
PREMIUM_MONTHS         = [3,6,12]
PREMIUM_PRICES         = {3:4.2,6:5.6,12:10}
premium_selection      = {}
pending_premium_orders = {}
ai_sessions = set()

# === Common Buttons ===
BTN_CANCEL = InlineKeyboardButton("❌", callback_data="start_over")

# --------------------------------------------------------------------------- #
#                              Firebase Helpers                               #
# --------------------------------------------------------------------------- #
def check_user(uid):
    return db.child("users").child(uid).get().val() is not None

def create_user(uid, username):
    db.child("users").child(uid).set({
        "username":          username or "",
        "balance":           0.0,
        "is_admin":          False,
        "history":           [],
        "referrer":          "",
        "referrals_count":   0,
        "referrals_earned":  0.0,
        "lang":              ""
    })

def update_username(uid, username):
    db.child("users").child(uid).update({"username": username or ""})

def fetch_balance(uid):
    val = db.child("users").child(uid).child("balance").get().val()
    return float(val) if val else 0.0

def save_balance(uid, amount):
    db.child("users").child(uid).update({"balance": amount})

def append_history(uid, record):
    hist = db.child("users").child(uid).child("history").get().val() or []
    hist.append(record)
    db.child("users").child(uid).update({"history": hist})

def get_username(user):
    return user.username or user.first_name or "User"

def get_lang(uid):
    lang = db.child("users").child(uid).child("lang").get().val()
    return lang if lang in LANGUAGES else "en"


# --------------------------------------------------------------------------- #
#                              Localization                                   #
# --------------------------------------------------------------------------- #

def t(uid, key, **kwargs):
    lang = get_lang(uid)
    texts = {
        "choose_lang": {
            "en": "Please select your language:",
            "ru": "Пожалуйста, выберите язык:"
        },
        "welcome": {
            "en": (
                "⭐ Welcome, <code>@{username}</code>!\n\n"
                "🆔 Your ID: <code>{user_id}</code>\n\n"
                "<i>Note: Stars, Numbers, AI & Premium purchases available now.\n\n</i>"
                "5% off all items for PUNK NFT holders! To redeem, send /discount"
            ),
            "ru": (
                "⭐ Добро пожаловать, <code>@{username}</code>!\n\n"
                "🆔 Ваш ID: <code>{user_id}</code>!\n\n"
                "<i>Примечание: доступны звёзды, номера, AI и премиум.</i>\n\n"
                "Скидка 5% на все товары для держателей NFT PUNK! отправьте команду /discount"
            )
        },
        "wallet": {
            "en": "💳 *Your Wallet*\n\nBalance: {bal:.2f} TON",
            "ru": "💳 *Ваш кошелёк*\n\nБаланс: {bal:.2f} TON"
        },
       # В локализации замените на:

    # …
    'top_up': {
        'en': (
            "1️⃣ *Copy Address:*\n"
            "    `{address}`\n\n"
            "2️⃣ *Send any amount of TON*\n\n"
            "3️⃣ *Use Memo:*\n"
            "    `{memo}`\n\n"
            "_Window expires in 20 minutes._"
        ),
        'ru': (
            "1️⃣ *Скопируйте адрес:*\n"
            "    `{address}`\n\n"
            "2️⃣ *Отправьте любое количество TON*\n\n"
            "3️⃣ *Используйте memo:*\n"
            "    `{memo}`\n\n"
            "_Окно закрывается через 20 минут._"
        )
    },
        "no_balance": {
            "en": "❌ Insufficient balance.",
            "ru": "❌ Недостаточно средств."
        },
        "services": {
            "en": "🛠 *Our Services*",
            "ru": "🛠 *Наши Сервисы*"
        },
        "coming_soon": {
            "en": "🚧 Coming soon!",
            "ru": "🚧 Скоро будет!"
        },
        "enter_username": {
            "en": "🛒 Enter the @username of the recipient:",
            "ru": "🛒 Введите @username получателя:"
        }
        # при необходимости добавьте здесь другие ключи (например, history)
    }
    return texts[key][lang].format(**kwargs)


# --------------------------------------------------------------------------- #
#                              Welcome & Menu                                 #
# --------------------------------------------------------------------------- #

@bot.message_handler(commands=['start'])
def cmd_start(msg):
    uid = str(msg.from_user.id)
    # 1) Проверяем, что у пользователя есть @username
    if not msg.from_user.username:
        lang = get_lang(uid)
        bot.send_message(
            msg.chat.id,
            "🚫 Please set a @username in your Telegram settings so the bot can work correctly."
            if lang == "en"
            else "🚫 Пожалуйста, установите @username в настройках Telegram, чтобы бот работал.",
        )
        return

    uname = get_username(msg.from_user)
    parts = msg.text.split()
    is_new = not check_user(uid)
    if is_new:
        create_user(uid, uname)
        # реферальная логика, если нужно
        if len(parts) > 1 and parts[1] != uid and check_user(parts[1]):
            db.child("users").child(uid).update({"referrer": parts[1]})
            cnt = db.child("users").child(parts[1]).child("referrals_count").get().val() or 0
            db.child("users").child(parts[1]).update({"referrals_count": cnt + 1})
        # показываем выбор языка
        kb = InlineKeyboardMarkup(row_width=2)
        for code, label in LANGUAGES.items():
            kb.add(InlineKeyboardButton(label, callback_data=f"set_lang_{code}"))
        bot.send_message(msg.chat.id, t(uid, "choose_lang"), reply_markup=kb)
    else:
        update_username(uid, uname)
        send_welcome(msg.chat.id, uid, uname)

@bot.callback_query_handler(lambda c: c.data.startswith("set_lang_"))
def cb_set_lang(c):
    bot.answer_callback_query(c.id)
    uid = str(c.from_user.id)
    lang = c.data.split("_")[2]
    db.child("users").child(uid).update({"lang": lang})
    bot.delete_message(c.message.chat.id, c.message.message_id)
    send_welcome(c.message.chat.id, uid, get_username(c.from_user))

@bot.callback_query_handler(lambda c: c.data == "start_over")
def cb_start_over(c):
    bot.answer_callback_query(c.id)
    bot.delete_message(c.message.chat.id, c.message.message_id)
    send_welcome(c.message.chat.id, str(c.from_user.id), get_username(c.from_user))

def send_welcome(chat_id, uid, username):
    caption = t(uid, "welcome", username=username, user_id=uid)
    lang = get_lang(uid)
    kb = InlineKeyboardMarkup(row_width=2)
    btn_wallet   = "💼 Wallet"    if lang=="en" else "💼 Кошелёк"
    btn_services = "🌟 Services"  if lang=="en" else "🌟 Сервисы"
    btn_channel  = "📺 Channel"   if lang=="en" else "📺 Канал"
    btn_support  = "✉️ Support"   if lang=="en" else "✉️ Поддержка"
    btn_refs     = "👥 Referrals" if lang=="en" else "👥 Рефералы"

    kb.add(
        InlineKeyboardButton(btn_wallet,   callback_data="wallet"),
        InlineKeyboardButton(btn_services, callback_data="services")
    )
    kb.add(
        InlineKeyboardButton(btn_channel,  url=f"https://t.me/{CHANNEL_NAME}"),
        InlineKeyboardButton(btn_support,  url=f"https://t.me/{SUPPORT_USER}")
    )
    kb.add(InlineKeyboardButton(btn_refs, callback_data="referrals"))

    bot.send_animation(
        chat_id,
        WELCOME_GIF,
        caption=caption,
        parse_mode="HTML",     # важно для HTML-разметки
        reply_markup=kb
    )

# --------------------------------------------------------------------------- #
#                               Wallet Flow                                   #
# --------------------------------------------------------------------------- #
@bot.callback_query_handler(lambda c: c.data=="wallet")
def cb_wallet(c):
    bot.answer_callback_query(c.id)
    bot.delete_message(c.message.chat.id, c.message.message_id)
    uid = str(c.from_user.id)
    bal = fetch_balance(uid)
    caption = t(uid, "wallet", bal=bal)
    lang = get_lang(uid)
    btn_top_up = "💸 Top Up" if lang=="en" else "💸 Пополнить"
    btn_hist   = "🗒 History" if lang=="en" else "🗒 История"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(btn_top_up, callback_data="top_up"),
        InlineKeyboardButton(btn_hist,   callback_data="history"),
        BTN_CANCEL
    )
    msg = bot.send_animation(c.message.chat.id, WALLET_GIF, caption=caption, reply_markup=kb)
    threading.Timer(1200, lambda: bot.delete_message(msg.chat.id, msg.message_id)).start()

# --------------------------------------------------------------------------- #
#                            Services & Submenus                              #
# --------------------------------------------------------------------------- #

@bot.callback_query_handler(lambda c: c.data == "services")
def cb_services(c):
    bot.answer_callback_query(c.id)
    bot.delete_message(c.message.chat.id, c.message.message_id)

    uid     = str(c.from_user.id)
    caption = t(uid, "services")
    lang    = get_lang(uid)

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(
            "⭐Stars & Premium" if lang=="en" else "⭐Stars & Premium",
            callback_data="telegram_services"
        ),
        InlineKeyboardButton(
            "🛡 VPN" if lang=="en" else "🛡 VPN ",
            callback_data="vpn"
        )
    )
    kb.add(
        InlineKeyboardButton(
            "New Account Number" if lang=="en" else "☎️ Новый номер",
            callback_data="buy_number"
        ),
        InlineKeyboardButton(
            "🎮 Entertainment" if lang=="en" else "🎮 Развлечения",
            callback_data="entertainment"
        )
    )
    kb.add(
        InlineKeyboardButton(
            "✨ AI Tools" if lang=="en" else "✨ AI ",
            callback_data="ai"
        ),
        InlineKeyboardButton(
            "💻 Dev Zone" if lang=="en" else "💻 Зона Разраб.",
            callback_data="dev_zone"
        )
    )
    kb.add(BTN_CANCEL)
    bot.send_photo(c.message.chat.id, SERVICE_IMG, caption=caption, reply_markup=kb)




@bot.callback_query_handler(lambda c: c.data == "entertainment")
def cb_entertainment(c):
    bot.answer_callback_query(c.id)
    bot.delete_message(c.message.chat.id, c.message.message_id)

    uid  = str(c.from_user.id)
    lang = get_lang(uid)
    text = (
        "🎮 *Entertainment Services*\n\n"
        "• *District Clash* — capture districts, PvP battles, upgrade fighters, earn PUNK tokens.\n\n"
        "• *Punk City* — TON blockchain PvP bot with NFT avatars and Play-to-Earn."
        if lang=="en" else
        "🎮 *Сервисы развлечений*\n\n"
        "• *District Clash* — захват районов, PvP-сражения, прокачка бойцов, заработок токенов PUNK.\n\n"
        "• *Punk City* — бот на блокчейне TON для PvP с NFT-аватарами и механикой Play-to-Earn."
    )
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🎮 District Clash", url="https://t.me/districtclash_bot"),
        InlineKeyboardButton("🎮 Punk City",       url="https://t.me/PunkCity2094bot"),
        InlineKeyboardButton(
            "🔙 Back to Services" if lang=="en" else "🔙 Назад к сервисам",
            callback_data="services"
        )
    )
    bot.send_message(c.message.chat.id, text, reply_markup=kb)


# generic “coming soon” для VPN и Dev Zone
for key in ["vpn", "dev_zone"]:
    @bot.callback_query_handler(lambda c, k=key: c.data == k)
    def cb_coming_soon(c, k=key):
        bot.answer_callback_query(c.id)
        bot.delete_message(c.message.chat.id, c.message.message_id)

        uid  = str(c.from_user.id)
        lang = get_lang(uid)
        kb   = InlineKeyboardMarkup().add(
            InlineKeyboardButton(
                "🔙 Back to Services" if lang=="en" else "🔙 Назад к сервисам",
                callback_data="services"
            )
        )
        bot.send_message(c.message.chat.id, t(uid, "coming_soon"), reply_markup=kb)


@bot.callback_query_handler(lambda c: c.data == "telegram_services")
def cb_telegram_services(c):
    bot.answer_callback_query(c.id)
    bot.delete_message(c.message.chat.id, c.message.message_id)

    uid     = str(c.from_user.id)
    lang    = get_lang(uid)
    caption = "✨ *Telegram Services*" if lang=="en" else "✨ *Сервисы Telegram*"

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(
            "⭐ Buy Stars" if lang=="en" else "⭐ Купить звёзды",
            callback_data="buy_stars"
        ),
        InlineKeyboardButton(
            "🎁 Buy Premium" if lang=="en" else "🎁 Купить премиум",
            callback_data="buy_premium"
        ),
        BTN_CANCEL
    )
    bot.send_message(c.message.chat.id, caption, reply_markup=kb)

# --------------------------------------------------------------------------- #
#                               Transaction History                           #
# --------------------------------------------------------------------------- #
@bot.callback_query_handler(lambda c: c.data=="history")
def cb_history(c):
    bot.answer_callback_query(c.id)
    bot.delete_message(c.message.chat.id, c.message.message_id)
    uid = str(c.from_user.id)
    lang = get_lang(uid)
    hist = db.child("users").child(uid).child("history").get().val() or []
    title = "🗒 *Transaction History:*" if lang=="en" else "🗒 *История транзакций:*"
    body = "\n".join(f"• {l}" for l in hist) if hist else ("— no records —" if lang=="en" else "— записей нет —")
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🔙 Back to Wallet" if lang=="en" else "🔙 Назад в кошелёк", callback_data="wallet")
    )
    bot.send_message(c.message.chat.id, f"{title}\n\n{body}", reply_markup=kb)



# --------------------------------------------------------------------------- #
#                               Transaction top up                           #
# --------------------------------------------------------------------------- #
@bot.callback_query_handler(lambda c: c.data == "top_up")
def cb_top_up(c):
    bot.answer_callback_query(c.id)
    bot.delete_message(c.message.chat.id, c.message.message_id)

    uid  = str(c.from_user.id)
    memo = uuid.uuid4().hex

    # Формируем инструкцию
    text = t(uid, "top_up", address=DEPOSIT_ADDRESS, memo=memo)
    lang = get_lang(uid)
    kb = InlineKeyboardMarkup() \
        .add(
            InlineKeyboardButton(
                "💰 Open Wallet" if lang == "en" else "💰 Открыть кошелёк",
                url=f"ton://transfer/{DEPOSIT_ADDRESS}?text={memo}"
            )
        ) \
        .add(
            InlineKeyboardButton("❌", callback_data="wallet")
        )

    instr_msg = bot.send_message(c.message.chat.id, text, reply_markup=kb)

    # Сохраняем memo → пользователь + id инструкции
    pending_topup_memos[memo] = {
        "uid":    uid,
        "msg_id": instr_msg.message_id
    }

    # Удалим инструкцию через 20 минут на всякий случай
    threading.Timer(
        1200,
        lambda: bot.delete_message(instr_msg.chat.id, instr_msg.message_id)
    ).start()


# 2) Декодер memo
def decode_memo(hex_or_plain: str) -> str:
    try:
        return bytes.fromhex(hex_or_plain).decode("utf-8")
    except Exception:
        return hex_or_plain


# 3) Фоновая функция-пуллер для обработки входящих транзакций (Top-Up с «интеллектуальным» polling)
session = requests.Session()
session.params = {
    "address":  DEPOSIT_ADDRESS,
    "limit":    50,
    "archival": "true",
    "api_key":  TON_API_KEY
}

def poll_deposits():
    while True:
        # если нет активных ожиданий пополнений — ждём дольше
        if not pending_topup_memos:
            time.sleep(50)
            continue

        try:
            resp = session.get(f"{API_BASE_URL}/api/v2/getTransactions", timeout=10).json()
            if not resp.get("ok"):
                time.sleep(20)
                continue

            for tx in resp["result"]:
                lt   = int(tx["transaction_id"]["lt"])
                memo = decode_memo(tx["in_msg"].get("message",""))

                # Если это наш memo и новая lt:
                if memo in pending_topup_memos and lt > last_topup_lts.get(memo, 0):
                    last_topup_lts[memo] = lt
                    entry = pending_topup_memos.pop(memo)
                    uid   = entry["uid"]
                    msg_id = entry.get("msg_id")
                    amount = int(tx["in_msg"]["value"]) / 1e9

                    # удаляем инструкцию
                    if msg_id:
                        try: bot.delete_message(int(uid), msg_id)
                        except: pass

                    # зачисляем баланс
                    new_bal = fetch_balance(uid) + amount
                    save_balance(uid, new_bal)
                    append_history(uid, f"Deposited {amount:.2f} TON")

                    # отправляем подтверждение
                    lang = get_lang(uid)
                    kb = InlineKeyboardMarkup().add(
                        InlineKeyboardButton(
                            "🔙 Back to Wallet" if lang=="en"
                            else "🔙 Назад в кошелёк",
                            callback_data="wallet"
                        )
                    )
                    bot.send_message(
                        int(uid),
                        (f"✅ Deposit {amount:.2f} TON confirmed.\n"
                         f"💳 New balance: {new_bal:.2f} TON")
                        if lang=="en" else
                        (f"✅ Пополнение {amount:.2f} TON подтверждено.\n"
                         f"💳 Новый баланс: {new_bal:.2f} TON"),
                        reply_markup=kb
                    )

        except Exception as e:
            logging.error(f"Deposit polling error: {e}")

        # между «активным» опросом — короткая пауза
        time.sleep(5)


# 4) Запуск фонового потока (раз в начале main)
threading.Thread(target=poll_deposits, daemon=True).start()

# --------------------------------------------------------------------------- #
#                           Price-helper: NFT discount                        #
# --------------------------------------------------------------------------- #
DISCOUNT_PCT = 0.05          # 5 %

def apply_discount(uid: str, price: float) -> float:
    """
    Возвращает цену с учётом скидки, если у пользователя есть отметка has_nft=True.
    Округляем до 3-х знаков (того требует интерфейс).
    """
    try:
        has_nft = db.child("users").child(uid).child("has_nft").get().val() or False
    except Exception:
        has_nft = False

    return round(price * (1 - DISCOUNT_PCT), 3) if has_nft else price

# ── Virtual Number Purchase (USA only, auto-expire after 10 min) ────────────

import threading

number_selection = {}  # uid → {"service", "activation", "chat_id", "msg_id", "timer"}

def expire_order(uid):
    sel = number_selection.get(uid)
    if not sel or sel.get("expired"):
        return
    act_id = sel.get("activation")
    if not act_id:
        return
    # check for code
    resp = requests.get(
        f'https://5sim.net/v1/user/check/{act_id}',
        headers={'Authorization':f'Bearer {SIM_TOKEN}','Accept':'application/json'}
    ).json()
    code = resp.get("code") or (resp.get("sms","") and resp["sms"][0])
    if code:
        return  # SMS arrived, do nothing
    # cancel at provider side
    requests.get(
        f'https://5sim.net/v1/user/cancel/{act_id}',
        headers={'Authorization':f'Bearer {SIM_TOKEN}','Accept':'application/json'}
    )
    # edit user message to indicate expiry
    chat_id = sel["chat_id"]
    msg_id  = sel["msg_id"]
    lang    = get_lang(uid)
    text = (
        "⌛ Time expired. Number validity ended."
        if lang=="en"
        else "⌛ Время истекло. Срок действия номера закончился."
    )
    # only "Done" button remains
    done = "❌ Done" if lang=="en" else "❌ Готово"
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton(done, callback_data="services")
    )
    bot.edit_message_text(text, chat_id, msg_id, parse_mode="Markdown", reply_markup=kb)
    sel["expired"] = True
    # clean up
    number_selection.pop(uid, None)


@bot.callback_query_handler(lambda c: c.data == "buy_number")
def cb_buy_number(c):
    bot.answer_callback_query(c.id)
    bot.delete_message(c.message.chat.id, c.message.message_id)
    uid, lang = str(c.from_user.id), get_lang(str(c.from_user.id))

    number_selection[uid] = {"chat_id": c.message.chat.id}

    caption = (
        "📞 *Virtual Number (USA)*\n\n"
        "• Keep your real number private\n"
        "• Receive SMS codes securely\n"
        "• Use it to register a Telegram account—it’s yours forever."
        if lang=="en"
        else
        "📞 *Виртуальный номер (USA)*\n\n"
        "• Сохраняйте реальный номер в тайне\n"
        "• Принимайте SMS-коды безопасно\n"
        "• Зарегистрируйте на нём Telegram-аккаунт — он останется вашим навсегда."
    )
    buy = "📱 Buy Number" if lang=="en" else "📱 Купить номер"
    cancel = "🛑 Cancel"   if lang=="en" else "🛑 Отмена"

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(buy,    callback_data="buy_number_confirm"),
        InlineKeyboardButton(cancel, callback_data="services")
    )
    msg = bot.send_message(c.message.chat.id, caption,
                           parse_mode="Markdown", reply_markup=kb)
    number_selection[uid]["msg_id"] = msg.message_id


@bot.callback_query_handler(lambda c: c.data == "buy_number_confirm")
def cb_buy_number_confirm(c):
    bot.answer_callback_query(c.id)
    uid, lang = str(c.from_user.id), get_lang(str(c.from_user.id))
    price = apply_discount(uid, 0.999)

    prompt = (
        f"Select a service (USA) — {price:.3f} TON per number:"
        if lang=="en"
        else
        f"Выберите сервис (USA) — {price:.3f} TON за номер:"
    )
    kb = InlineKeyboardMarkup(row_width=3)
    for svc in NUMBER_SERVICES:
        kb.add(InlineKeyboardButton(svc.title(), callback_data=f"svc:{svc}"))
    kb.add(InlineKeyboardButton("🛑 Cancel" if lang=="en" else "🛑 Отмена",
                                callback_data="services"))

    bot.edit_message_text(prompt,
                          c.message.chat.id,
                          number_selection[uid]["msg_id"],
                          parse_mode="Markdown", reply_markup=kb)


@bot.callback_query_handler(lambda c: c.data.startswith("svc:"))
def cb_choose_service(c):
    bot.answer_callback_query(c.id)
    uid = str(c.from_user.id)
    svc = c.data.split(":",1)[1]
    number_selection[uid]["service"] = svc
    lang = get_lang(uid)
    price = apply_discount(uid, 0.999)

    text = (
        f"✅ Confirm purchase of *{svc.title()}* number for *{price:.3f} TON*?\n\n"
        "_Valid for 10 minutes._"
        if lang=="en"
        else
        f"✅ Подтвердите покупку *{svc.title()}* номера за *{price:.3f} TON*?\n\n"
        "_Номер действителен 10 минут._"
    )
    yes = "✅ Yes" if lang=="en" else "✅ Да"
    no  = "🛑 Cancel" if lang=="en" else "🛑 Отмена"

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(yes, callback_data="confirm_buy"),
        InlineKeyboardButton(no,  callback_data="services")
    )

    bot.edit_message_text(text,
                          number_selection[uid]["chat_id"],
                          number_selection[uid]["msg_id"],
                          parse_mode="Markdown", reply_markup=kb)


@bot.callback_query_handler(lambda c: c.data == "confirm_buy")
def cb_confirm_buy(c):
    bot.answer_callback_query(c.id)
    uid = str(c.from_user.id)
    sel = number_selection.get(uid, {})
    svc = sel.get("service")
    lang = get_lang(uid)
    bal  = fetch_balance(uid)
    price = apply_discount(uid, 0.999)

    if bal < price:
        return bot.send_message(sel["chat_id"], t(uid, "no_balance"))

    # request number
    resp = requests.get(
        f'https://5sim.net/v1/user/buy/activation/usa/any/{svc}',
        headers={'Authorization':f'Bearer {SIM_TOKEN}','Accept':'application/json'}
    ).json()
    phone = resp.get("phone")
    act_id= resp.get("id")

    if not phone:
        # no numbers available
        msg = ("No numbers available, try later." if lang=="en"
               else "Номеров нет, попробуйте позже.")
        bot.send_message(sel["chat_id"], msg)
        return cb_buy_number(c)  # go back to menu

    # deduct user balance
    save_balance(uid, bal - price)
    append_history(uid, f"Bought {svc} number {phone}")
    sel["activation"] = act_id

    # send final message
    text = (
        f"✅ Your number: `{phone}`\n\n"
        "Refresh for SMS code or exit."
        if lang=="en"
        else
        f"✅ Ваш номер: `{phone}`\n\n"
        "Обновите для кода или выход."
    )
    refresh = "🔄 Refresh Code" if lang=="en" else "🔄 Обновить код"
    done    = "❌ Done"           if lang=="en" else "❌ Готово"

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(refresh, callback_data="get_code"),
        InlineKeyboardButton(done,    callback_data="services")
    )

    m = bot.send_message(sel["chat_id"], text, parse_mode="Markdown", reply_markup=kb)
    sel["msg_id"] = m.message_id

    # schedule automatic expiry after 10 minutes
    timer = threading.Timer(600, lambda uid=uid: expire_order(uid))
    sel["timer"] = timer
    timer.start()


@bot.callback_query_handler(lambda c: c.data == "get_code")
def cb_get_code(c):
    bot.answer_callback_query(c.id)
    uid = str(c.from_user.id)
    sel = number_selection.get(uid, {})
    act_id = sel.get("activation")
    lang = get_lang(uid)
    if not act_id or sel.get("expired"):
        return bot.send_message(c.message.chat.id,
            "Order expired." if lang=="en" else "Срок заказа истёк.")
    resp = requests.get(
        f'https://5sim.net/v1/user/check/{act_id}',
        headers={'Authorization':f'Bearer {SIM_TOKEN}','Accept':'application/json'}
    ).json()
    code = resp.get("code") or (resp.get("sms","") and resp["sms"][0])
    if not code:
        msg = ("No code yet. Try again later." if lang=="en"
               else "Код ещё не пришёл. Попробуйте позже.")
    else:
        msg = f"🔢 SMS Code: *{code}*"
    # same vertical buttons
    refresh = "🔄 Refresh Code" if lang=="en" else "🔄 Обновить код"
    done    = "❌ Done"           if lang=="en" else "❌ Готово"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(refresh, callback_data="get_code"),
        InlineKeyboardButton(done,    callback_data="services")
    )
    bot.send_message(c.message.chat.id, msg, parse_mode="Markdown", reply_markup=kb)


# ── BUY TELEGRAM STARS (Revised) ─────────────────────────────────────────────

STAR_IMG_URL = "https://raw.githubusercontent.com/qnexst/404token/main/star.jpg"

@bot.callback_query_handler(lambda c: c.data == "buy_stars")
def cb_buy_stars(c):
    bot.answer_callback_query(c.id)
    bot.delete_message(c.message.chat.id, c.message.message_id)

    uid = str(c.from_user.id)
    star_selection[uid] = {
        "qty":       TARIFFS[0],
        "recipient": get_username(c.from_user),
        "chat_id":   c.message.chat.id,
        "msg_id":    None
    }
    show_star_menu(uid, force_new=True)


def show_star_menu(uid, *, force_new=False):
    """Draw or update the Stars purchase menu as a photo with inline buttons."""
    sel = star_selection.get(uid)
    if not sel:
        return

    chat_id = sel["chat_id"]
    msg_id  = sel.get("msg_id")
    qty      = sel["qty"]
    rec      = sel["recipient"]
    price    = apply_discount(uid, STAR_PRICES[qty])
    lang     = get_lang(uid)

    # build caption without balance text
    if lang == "en":
        caption = (
            f"💫 *Purchase Telegram Stars*\n\n"
            f"Recipient: <b>@{rec}</b>\n"
            f"Quantity: <b>{qty}</b> → <b>{price:.3f} TON</b>"
        )
    else:
        caption = (
            f"💫 *Покупка звёзд Telegram*\n\n"
            f"Получатель: <b>@{rec}</b>\n"
            f"Количество: <b>{qty}</b> → <b>{price:.3f} TON</b>"
        )

    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("➖", callback_data="stars_minus"),
        InlineKeyboardButton("💰 Buy", callback_data="stars_continue"),
        InlineKeyboardButton("➕", callback_data="stars_plus")
    )
    kb.add(
        InlineKeyboardButton("🔄 Change Recipient", callback_data="stars_change"),
        InlineKeyboardButton("🛑 Cancel",            callback_data="telegram_services")
    )
    kb.add(
        InlineKeyboardButton("💳 My Balance", callback_data="star_balance")
    )

    # if existing message, edit caption; else send new photo
    if msg_id and not force_new:
        try:
            bot.edit_message_caption(
                caption=caption,
                chat_id=chat_id,
                message_id=msg_id,
                parse_mode="HTML",
                reply_markup=kb
            )
            return
        except Exception:
            pass

    # delete old menu if present
    if msg_id:
        try: bot.delete_message(chat_id, msg_id)
        except: pass

    m = bot.send_photo(
        chat_id,
        STAR_IMG_URL,
        caption=caption,
        parse_mode="HTML",
        reply_markup=kb
    )
    sel["msg_id"] = m.message_id


@bot.callback_query_handler(lambda c: c.data in ["stars_minus", "stars_plus"])
def cb_stars_adjust(c):
    uid = str(c.from_user.id)
    sel = star_selection.get(uid)
    if not sel:
        return bot.answer_callback_query(c.id)

    idx = TARIFFS.index(sel["qty"])
    lang = get_lang(uid)

    if c.data == "stars_minus":
        if idx == 0:
            return bot.answer_callback_query(
                c.id,
                text="Минимум достигнут" if lang=="ru" else "Minimum reached",
                show_alert=True
            )
        idx -= 1

    if c.data == "stars_plus":
        if idx == len(TARIFFS) - 1:
            return bot.answer_callback_query(
                c.id,
                text="Максимум достигнут" if lang=="ru" else "Maximum reached",
                show_alert=True
            )
        idx += 1

    sel["qty"] = TARIFFS[idx]
    show_star_menu(uid)


@bot.callback_query_handler(lambda c: c.data == "stars_change")
def cb_stars_change(c):
    bot.answer_callback_query(c.id)
    uid, lang = str(c.from_user.id), get_lang(str(c.from_user.id))
    prompt = "Enter @username:" if lang=="en" else "Введите @username:"
    m = bot.send_message(uid, prompt, reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("❌ Cancel", callback_data="telegram_services")
    ))
    bot.register_next_step_handler(m, process_star_username)


def process_star_username(msg):
    uid = str(msg.from_user.id)
    sel = star_selection.get(uid)
    if not sel:
        return
    new_u = msg.text.strip().lstrip("@")
    lang  = get_lang(uid)
    if not new_u:
        retry = "Invalid username, try again:" if lang=="en" else "Неверный username, попробуйте снова:"
        m = bot.send_message(uid, retry)
        bot.register_next_step_handler(m, process_star_username)
        return
    sel["recipient"] = new_u
    show_star_menu(uid, force_new=True)


@bot.callback_query_handler(lambda c: c.data == "stars_continue")
def cb_stars_continue(c):
    bot.answer_callback_query(c.id)
    uid = str(c.from_user.id)
    sel = star_selection.get(uid)
    if not sel:
        return

    qty   = sel["qty"]
    price = apply_discount(uid, STAR_PRICES[qty])
    lang  = get_lang(uid)
    label = f"{qty} Stars"
    if lang == "en":
        caption = f"✅ Confirm purchase of *{label}* for *{price:.3f} TON*?"
    else:
        caption = f"✅ Подтвердите покупку *{label}* за *{price:.3f} TON*?"

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Yes", callback_data="stars_confirm"),
        InlineKeyboardButton("❌ No",  callback_data="telegram_services")
    )

    bot.edit_message_caption(
        caption=caption,
        chat_id=sel["chat_id"],
        message_id=sel["msg_id"],
        parse_mode="Markdown",
        reply_markup=kb
    )


@bot.callback_query_handler(lambda c: c.data == "stars_confirm")
def cb_stars_confirm(c):
    bot.answer_callback_query(c.id)
    uid = str(c.from_user.id)
    sel = star_selection.pop(uid, None)
    if not sel:
        return

    qty   = sel["qty"]
    price = apply_discount(uid, STAR_PRICES[qty])
    bal   = fetch_balance(uid)
    if bal < price:
        return bot.send_message(sel["chat_id"], t(uid, "no_balance"))

    save_balance(uid, bal - price)
    append_history(uid, f"Ordered {qty} Stars for @{sel['recipient']}")

    order_id = uuid.uuid4().hex
    db.child("orders").child(order_id).set({
        "user_uid":  uid,
        "recipient": sel["recipient"],
        "qty":       qty,
        "status":    "pending",
        "type":      "stars"
    })

    link = f"https://fragment.com/stars/buy?quantity={qty}"
    for adm_uid, data in (db.child("users").get().val() or {}).items():
        if data.get("is_admin"):
            adm_text = (
                f"🆕 New Stars Order:\n"
                f"• User: @{sel['recipient']}\n"
                f"• Qty: {qty}\n"
                f"• Link: {link}\n"
                f"• Order ID: <code>{order_id}</code>\n"
                f"• Status: pending"
            )
            kb = InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Mark as Sent", callback_data=f"stars_sent:{order_id}")
            )
            bot.send_message(adm_uid, adm_text, parse_mode="HTML", reply_markup=kb)

    done = "✅ Order placed." if get_lang(uid)=="en" else "✅ Заказ создан."
    bot.send_message(sel["chat_id"], done)


@bot.callback_query_handler(lambda c: c.data == "star_balance")
def cb_star_balance(c):
    bot.answer_callback_query(c.id)
    uid = str(c.from_user.id)
    bal = fetch_balance(uid)
    text = f"💳 Your balance: <b>{bal:.3f} TON</b>" if get_lang(uid)=="en" else f"💳 Ваш баланс: <b>{bal:.3f} TON</b>"
    bot.send_message(c.message.chat.id, text, parse_mode="HTML")


@bot.callback_query_handler(lambda c: c.data.startswith("stars_sent:"))
def cb_stars_sent(c):
    bot.answer_callback_query(c.id)
    order_id = c.data.split(":",1)[1]
    order = db.child("orders").child(order_id).get().val() or {}
    if not order:
        return bot.send_message(c.message.chat.id, "❌ Order not found.")
    db.child("orders").child(order_id).update({"status":"sent"})

    user_uid  = order["user_uid"]
    qty       = order["qty"]
    recipient = order["recipient"]
    lang_u    = get_lang(user_uid)

    # notify user in their language
    msg = (
        f"✅ Your {qty} Stars for @{recipient} have been sent!"
        if lang_u=="en"
        else f"✅ Ваши {qty} звёзд для @{recipient} отправлены!"
    )
    bot.send_message(user_uid, msg)
    append_history(user_uid, f"Stars order {order_id} marked sent by admin")

    # update admin message
    new_text = f"✅ Order {order_id} marked as sent."
    bot.edit_message_text(new_text, c.message.chat.id, c.message.message_id)

# ── BUY TELEGRAM PREMIUM (Improved) ─────────────────────────────────────────

@bot.callback_query_handler(lambda c: c.data == "buy_premium")
def cb_buy_premium(c):
    bot.answer_callback_query(c.id)
    bot.delete_message(c.message.chat.id, c.message.message_id)

    uid = str(c.from_user.id)
    premium_selection[uid] = {
        "months":    PREMIUM_MONTHS[0],
        "recipient": get_username(c.from_user),
        "chat_id":   c.message.chat.id,
        "msg_id":    None
    }
    show_premium_menu(uid, force_new=True)


def show_premium_menu(uid, *, force_new=False):
    """Render or update the Premium purchase menu with extra features."""
    sel = premium_selection.get(uid)
    if not sel:
        return

    chat_id = sel["chat_id"]
    msg_id  = sel.get("msg_id")
    months  = sel["months"]
    rec     = sel["recipient"]
    orig    = PREMIUM_PRICES[months]
    price   = apply_discount(uid, orig)
    has_nft = db.child("users").child(uid).child("has_nft").get().val() or False
    lang    = get_lang(uid)

    # Header: NFT discount indicator
    header = "🎉 NFT discount applied!\n" if has_nft else ""

    if lang == "en":
        title   = "🔒 *Buy Telegram Premium*"
        rec_txt = f"Recipient: <b>@{rec}</b>"
        dur_txt = f"Duration: <b>{months} month{'s' if months>1 else ''}</b> → <b>{price:.3f} TON</b>"
    else:
        title   = "🔒 *Покупка Telegram Premium*"
        rec_txt = f"Получатель: <b>@{rec}</b>"
        dur_txt = f"Длительность: <b>{months} мес.</b> → <b>{price:.3f} TON</b>"

    text = f"{header}{title}\n\n{rec_txt}\n{dur_txt}"

    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("➖", callback_data="prem_minus"),
        InlineKeyboardButton("💰 Buy", callback_data="prem_continue"),
        InlineKeyboardButton("➕", callback_data="prem_plus")
    )
    kb.add(
        InlineKeyboardButton("🔄 Change Recipient", callback_data="prem_change"),
        InlineKeyboardButton("🛑 Cancel",             callback_data="telegram_services")
    )
    kb.add(
        InlineKeyboardButton("💳 My Balance", callback_data="premium_balance")
    )

    if msg_id and not force_new:
        try:
            bot.edit_message_text(
                text, chat_id, msg_id,
                parse_mode="HTML", reply_markup=kb
            )
            return
        except:
            pass

    if msg_id:
        try: bot.delete_message(chat_id, msg_id)
        except: pass

    m = bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)
    sel["msg_id"] = m.message_id


@bot.callback_query_handler(lambda c: c.data in ["prem_minus", "prem_plus"])
def cb_prem_adjust(c):
    uid = str(c.from_user.id)
    sel = premium_selection.get(uid)
    if not sel:
        return bot.answer_callback_query(c.id)

    idx  = PREMIUM_MONTHS.index(sel["months"])
    lang = get_lang(uid)

    if c.data == "prem_minus":
        if idx == 0:
            return bot.answer_callback_query(
                c.id,
                text="Минимум достигнут" if lang=="ru" else "Minimum reached",
                show_alert=True
            )
        idx -= 1

    if c.data == "prem_plus":
        if idx == len(PREMIUM_MONTHS) - 1:
            return bot.answer_callback_query(
                c.id,
                text="Максимум достигнут" if lang=="ru" else "Maximum reached",
                show_alert=True
            )
        idx += 1

    sel["months"] = PREMIUM_MONTHS[idx]
    show_premium_menu(uid)


@bot.callback_query_handler(lambda c: c.data == "prem_change")
def cb_prem_change(c):
    bot.answer_callback_query(c.id)
    uid, lang = str(c.from_user.id), get_lang(str(c.from_user.id))
    prompt = "Enter @username:" if lang=="en" else "Введите @username:"
    m = bot.send_message(uid, prompt, reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("❌ Cancel", callback_data="telegram_services")
    ))
    bot.register_next_step_handler(m, process_prem_username)


def process_prem_username(msg):
    uid = str(msg.from_user.id)
    sel = premium_selection.get(uid)
    if not sel:
        return

    new_u = msg.text.strip().lstrip("@")
    lang  = get_lang(uid)
    if not new_u:
        retry = "Invalid username, try again:" if lang=="en" else "Неверный username, попробуйте снова:"
        m = bot.send_message(uid, retry)
        bot.register_next_step_handler(m, process_prem_username)
        return

    sel["recipient"] = new_u
    show_premium_menu(uid, force_new=True)


@bot.callback_query_handler(lambda c: c.data == "prem_continue")
def cb_prem_continue(c):
    bot.answer_callback_query(c.id)
    uid = str(c.from_user.id)
    sel = premium_selection.get(uid)
    if not sel:
        return

    months = sel["months"]
    base   = PREMIUM_PRICES[months]
    price  = apply_discount(uid, base)
    lang   = get_lang(uid)
    label  = f"{months} month{'s' if months>1 else ''}" if lang=="en" else f"{months} мес."
    if lang == "en":
        text = f"✅ Confirm purchase of *{label} Premium* for *{price:.3f} TON*?"
    else:
        text = f"✅ Подтвердите покупку Premium *{label}* за *{price:.3f} TON*?"

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Yes", callback_data="prem_confirm"),
        InlineKeyboardButton("❌ No",  callback_data="telegram_services")
    )

    bot.edit_message_text(
        text, sel["chat_id"], sel["msg_id"],
        parse_mode="Markdown", reply_markup=kb
    )


@bot.callback_query_handler(lambda c: c.data == "prem_confirm")
def cb_prem_confirm(c):
    bot.answer_callback_query(c.id)
    uid = str(c.from_user.id)
    sel = premium_selection.pop(uid, None)
    if not sel:
        return

    months = sel["months"]
    base   = PREMIUM_PRICES[months]
    price  = apply_discount(uid, base)
    bal    = fetch_balance(uid)
    lang   = get_lang(uid)

    if bal < price:
        return bot.send_message(sel["chat_id"], t(uid, "no_balance"))

    save_balance(uid, bal - price)
    append_history(uid, f"Ordered Premium {months}m for @{sel['recipient']}")

    order_id = uuid.uuid4().hex
    db.child("orders").child(order_id).set({
        "user_uid":  uid,
        "recipient": sel["recipient"],
        "months":    months,
        "status":    "pending",
        "type":      "premium"
    })

    # notify admins
    link = f"https://fragment.com/premium/gift?months={months}"
    for adm_uid, data in (db.child("users").get().val() or {}).items():
        if data.get("is_admin"):
            adm_text = (
                f"🆕 New Premium Order:\n"
                f"• User: @{sel['recipient']}\n"
                f"• Months: {months}\n"
                f"• Link: {link}\n"
                f"• Order ID: <code>{order_id}</code>\n"
                f"• Status: pending"
            )
            kb = InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Mark as Sent", callback_data=f"prem_sent:{order_id}")
            )
            bot.send_message(adm_uid, adm_text, parse_mode="HTML", reply_markup=kb)

    done = "✅ Order placed." if lang=="en" else "✅ Заказ создан."
    bot.send_message(sel["chat_id"], done)


@bot.callback_query_handler(lambda c: c.data == "premium_balance")
def cb_premium_balance(c):
    bot.answer_callback_query(c.id)
    uid = str(c.from_user.id)
    bal = fetch_balance(uid)
    text = f"💳 Your balance: <b>{bal:.3f} TON</b>" if get_lang(uid)=="en" else f"💳 Ваш баланс: <b>{bal:.3f} TON</b>"
    bot.send_message(c.message.chat.id, text, parse_mode="HTML")


@bot.callback_query_handler(lambda c: c.data.startswith("prem_sent:"))
def cb_prem_sent(c):
    bot.answer_callback_query(c.id)
    order_id = c.data.split(":",1)[1]
    order = db.child("orders").child(order_id).get().val() or {}
    if not order:
        return bot.send_message(c.message.chat.id, "❌ Order not found.")
    db.child("orders").child(order_id).update({"status":"sent"})

    user_uid  = order["user_uid"]
    months    = order["months"]
    recipient = order["recipient"]
    lang_u    = get_lang(user_uid)

    # notify user
    msg = (
        f"✅ Your {months} month{'s' if months>1 else ''} Premium for @{recipient} has been activated!"
        if lang_u=="en"
        else f"✅ Ваш Premium на {months} мес. для @{recipient} активирован!"
    )
    bot.send_message(user_uid, msg)
    append_history(user_uid, f"Premium order {order_id} marked sent by admin")

    # update admin message
    bot.edit_message_text(
        f"✅ Order {order_id} marked as sent.",
        c.message.chat.id, c.message.message_id
    )


# === AI Integration Section (With NFT Discount & Full “month” Labels) ===

import html
import threading
import time
import logging
import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ─── Configuration ─────────────────────────────────────────────────────────
AI21_API_KEY        = ""
AI21_MODEL          = "jamba-large"   # or "jamba-mini"
FREE_TRIAL_REQUESTS = 3               # free chat requests per user
AI_PLANS = {
    1: 0.5,    # 1 month
    3: 1.0,    # 3 months
    12: 3.50   # 12 months
}

# ─── In-memory store ────────────────────────────────────────────────────────
ai_sessions = set()

# ─── Helpers ───────────────────────────────────────────────────────────────
def _now() -> float:
    return time.time()

def _paid_until(uid: str) -> float:
    return db.child("users").child(uid).child("ai_exp").get().val() or 0.0

def _free_used(uid: str) -> int:
    return db.child("users").child(uid).child("free_ai_used").get().val() or 0

def remaining_free(uid: str) -> int:
    return max(0, FREE_TRIAL_REQUESTS - _free_used(uid))

def can_use_ai(uid: str) -> bool:
    return _now() < _paid_until(uid) or _free_used(uid) < FREE_TRIAL_REQUESTS

def _inc_free(uid: str):
    new_count = _free_used(uid) + 1
    db.child("users").child(uid).update({"free_ai_used": new_count})
    append_history(uid, f"AI free trial used ({new_count}/{FREE_TRIAL_REQUESTS})")

def grant_ai(uid: str, months: int):
    base   = max(_now(), _paid_until(uid))
    expiry = base + months * 30 * 24 * 3600
    db.child("users").child(uid).update({
        "ai_exp": expiry,
        "free_ai_used": 0
    })
    append_history(uid, f"Purchased AI plan: {months} month{'s' if months>1 else ''}")

def _keep_typing(bot, chat_id, stop_evt):
    while not stop_evt.is_set():
        try: bot.send_chat_action(chat_id, "typing")
        except: pass
        time.sleep(4)

def _ai21_chat(prompt: str) -> str:
    url = "https://api.ai21.com/studio/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI21_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": AI21_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user",   "content": prompt}
        ],
        "temperature": 0.7,
        "maxTokens": 300
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20).json()
        if "error" in resp:
            logging.error(f"AI21 error: {resp['error']}")
            return f"⚠️ API error: {resp['error'].get('message','Unknown')}"
        if "choices" not in resp:
            logging.error(f"Unexpected AI21 response: {resp}")
            return "⚠️ Unexpected response from AI21."
        return resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logging.error(f"AI21 failed: {e}")
        return "⚠️ Sorry, I can’t answer right now."

def _chunks(txt: str, n: int = 4000):
    for i in range(0, len(txt), n):
        yield txt[i:i+n]

# ─── UI & Handlers ─────────────────────────────────────────────────────────

def show_ai_center(chat_id: int, uid: str):
    lang = get_lang(uid)
    paid_expiry = _paid_until(uid)
    if _now() < paid_expiry:
        expiry_str = time.strftime("%Y-%m-%d", time.localtime(paid_expiry))
        status = f"🗓 Plan active until <b>{expiry_str}</b>."
    else:
        rem = remaining_free(uid)
        status = (f"🎁 Free requests left: <b>{rem}</b>/{FREE_TRIAL_REQUESTS}."
                  if rem>0 else "🚫 Free trial ended.")
    text = f"🤖 AI Center\n\n{status}" if lang=="en" else f"🤖 Центр ИИ\n\n{status}"
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💬 Chat with AI", callback_data="ai_chat"),
        InlineKeyboardButton("🖼 Generate Image", callback_data="ai_image")
    )
    kb.add(
        InlineKeyboardButton("🎙 Voice AI",      callback_data="ai_voice"),
        InlineKeyboardButton("📦 Plans & Pricing", callback_data="ai_plans")
    )
    back_label = "🔙 Back to Services" if lang=="en" else "🔙 Назад к сервисам"
    kb.add(InlineKeyboardButton(back_label, callback_data="services"))
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=["ai","AI"])
def cmd_ai(msg):
    uid = str(msg.from_user.id)
    show_ai_center(msg.chat.id, uid)

@bot.callback_query_handler(lambda c: c.data=="ai")
def cb_ai(c):
    bot.answer_callback_query(c.id)
    bot.delete_message(c.message.chat.id, c.message.message_id)
    show_ai_center(c.message.chat.id, str(c.from_user.id))

@bot.callback_query_handler(lambda c: c.data in ["ai_image","ai_voice"])
def cb_ai_soon(c):
    bot.answer_callback_query(c.id)
    lang = get_lang(str(c.from_user.id))
    text = "🚧 Coming soon!" if lang=="en" else "🚧 Скоро будет!"
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🔙 Back", callback_data="ai")
    )
    bot.send_message(c.message.chat.id, text, reply_markup=kb)

@bot.callback_query_handler(lambda c: c.data=="ai_plans")
def cb_ai_plans(c):
    bot.answer_callback_query(c.id)
    uid     = str(c.from_user.id)
    chat_id = c.message.chat.id
    lang    = get_lang(uid)
    text    = "🚀 Available AI plans:" if lang=="en" else "🚀 Доступные тарифы ИИ:"
    kb = InlineKeyboardMarkup(row_width=1)
    for months, base_price in AI_PLANS.items():
        label = f"{months} month" if months==1 else f"{months} months"
        price = apply_discount(uid, base_price)
        kb.add(InlineKeyboardButton(f"{label} — {price:.2f} TON", callback_data=f"ai_buy:{months}"))
    back_label = "⬅️ Back" if lang=="en" else "⬅️ Назад"
    kb.add(InlineKeyboardButton(back_label, callback_data="ai"))
    bot.edit_message_text(text, chat_id, c.message.message_id,
                          parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(lambda c: c.data.startswith("ai_buy:"))
def cb_ai_buy(c):
    bot.answer_callback_query(c.id)
    uid     = str(c.from_user.id)
    chat_id = c.message.chat.id
    months  = int(c.data.split(":",1)[1])
    base    = AI_PLANS[months]
    price   = apply_discount(uid, base)
    label   = f"{months} month" if months==1 else f"{months} months"
    text    = f"✅ Confirm purchase of <b>{label}</b> for <b>{price:.2f} TON</b>?"
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Yes", callback_data=f"ai_confirm:{months}"),
        InlineKeyboardButton("❌ Cancel", callback_data="ai_plans")
    )
    bot.edit_message_text(text, chat_id, c.message.message_id,
                          parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(lambda c: c.data.startswith("ai_confirm:"))
def cb_ai_confirm(c):
    bot.answer_callback_query(c.id)
    uid     = str(c.from_user.id)
    chat_id = c.message.chat.id
    months  = int(c.data.split(":",1)[1])
    base    = AI_PLANS[months]
    price   = apply_discount(uid, base)
    bal     = fetch_balance(uid)
    if bal < price:
        return bot.send_message(chat_id, t(uid,"no_balance"))
    save_balance(uid, bal - price)
    grant_ai(uid, months)
    lang = get_lang(uid)
    msg = "✅ AI plan activated!" if lang=="en" else "✅ AI-план активирован!"
    bot.send_message(chat_id, msg)
    show_ai_center(chat_id, uid)

@bot.callback_query_handler(lambda c: c.data=="ai_chat")
def cb_ai_chat(c):
    bot.answer_callback_query(c.id)
    uid     = str(c.from_user.id)
    chat_id = c.message.chat.id
    if not can_use_ai(uid):
        lang = get_lang(uid)
        kb   = InlineKeyboardMarkup().add(
            InlineKeyboardButton("📦 Plans & Pricing", callback_data="ai_plans")
        )
        return bot.send_message(chat_id,
            "🚫 Free trial ended. Please buy a plan." if lang=="en"
            else "🚫 Бесплатный триал закончился. Купите тариф.",
            reply_markup=kb
        )
    ai_sessions.add(uid)
    prompt = "🤖 Ask me anything:" if get_lang(uid)=="en" else "🤖 Задайте вопрос:"
    kb     = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🔚 Finish chat", callback_data="end_ai")
    )
    bot.send_message(chat_id, prompt, reply_markup=kb)

@bot.message_handler(func=lambda m: str(m.from_user.id) in ai_sessions)
def _ai_dialog(msg):
    uid     = str(msg.from_user.id)
    chat_id = msg.chat.id
    if not can_use_ai(uid):
        ai_sessions.discard(uid)
        lang = get_lang(uid)
        kb   = InlineKeyboardMarkup().add(
            InlineKeyboardButton("📦 Plans & Pricing", callback_data="ai_plans")
        )
        return bot.send_message(chat_id,
            "🚫 Free trial ended. Please buy a plan." if lang=="en"
            else "🚫 Бесплатный триал закончился. Купите тариф.",
            reply_markup=kb
        )
    stop_evt = threading.Event()
    threading.Thread(target=_keep_typing, args=(bot, chat_id, stop_evt), daemon=True).start()
    answer = _ai21_chat(msg.text)
    stop_evt.set()
    if _now() >= _paid_until(uid):
        _inc_free(uid)
    finish_kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🔚 Finish chat", callback_data="end_ai")
    )
    for chunk in _chunks(f"<pre>{html.escape(answer)}</pre>"):
        bot.send_message(chat_id, chunk,
                         parse_mode="HTML",
                         disable_web_page_preview=True,
                         reply_markup=finish_kb)

@bot.callback_query_handler(lambda c: c.data=="end_ai")
def cb_end_ai(c):
    bot.answer_callback_query(c.id)
    uid = str(c.from_user.id)
    ai_sessions.discard(uid)
    bot.delete_message(c.message.chat.id, c.message.message_id)
    show_ai_center(c.message.chat.id, uid)

# --------------------------------------------------------------------------- #
#                            Referrals Screen                                 #
# --------------------------------------------------------------------------- #
@bot.callback_query_handler(lambda c: c.data == "referrals")
def cb_referrals(c):
    logging.info(f"[Referrals] User {c.from_user.id} pressed referrals")
    try:
        bot.answer_callback_query(c.id)
        # Удаляем предыдущий интерфейс
        bot.delete_message(c.message.chat.id, c.message.message_id)

        uid     = str(c.from_user.id)
        lang    = get_lang(uid)
        cnt     = db.child("users").child(uid).child("referrals_count").get().val() or 0
        earned  = db.child("users").child(uid).child("referrals_earned").get().val() or 0.0
        link    = f"https://t.me/{BOT_USERNAME}?start={uid}"

        if lang == "en":
            text = (
                "👥 <b>Your Referrals</b>\n\n"
                "Referral bonus: 0.02 TON when a referral spends ≥ 1 TON.\n\n"
                f"You’ve invited <b>{cnt}</b> users.\n"
                f"Total earned: <b>{earned:.2f} TON</b>.\n\n"
                "Share your link:\n"
                f"<code>{link}</code>"
            )
            back_label = "🔙 Back"
        else:
            text = (
                "👥 <b>Ваши рефералы</b>\n\n"
                "Реферальный бонус: 0.02 TON, когда реферал тратит ≥ 1 TON.\n\n"
                f"Вы пригласили <b>{cnt}</b> пользователей.\n"
                f"Всего заработано: <b>{earned:.2f} TON</b>.\n\n"
                "Поделитесь ссылкой:\n"
                f"<code>{link}</code>"
            )
            back_label = "❌ Назад"

        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton(back_label, callback_data="start_over")
        )

        bot.send_message(
            c.message.chat.id,
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=kb
        )

    except Exception as e:
        logging.error(f"[Referrals] Error in cb_referrals: {e}")
        bot.send_message(c.message.chat.id, "⚠️ Произошла ошибка при получении информации о рефералах.")
# --------------------------------------------------------------------------- #
#                                  commands                               #
# --------------------------------------------------------------------------- #
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton

# --- зарегистрировать команды в меню рядом с вводом ---
bot.set_my_commands([
    BotCommand("/start",   "Start the bot"),
    BotCommand("/info",    "Show bot info"),
    BotCommand("/ai",      "Start AI session"),
    BotCommand("/buystars","Buy Stars & Premium"),
    BotCommand("/discount","NFT discount instructions"),
    BotCommand("/hosting","Host your static websites"),
])

# --- /info выводит текст с описанием на выбранном языке ---
@bot.message_handler(commands=["info"])
def cmd_info(msg):
    uid = str(msg.from_user.id)
    lang = get_lang(uid)  # "en" или "ru"
    
    if lang == "ru":
         info_text = (
    "🤖 *Arion_Dbot — универсальный помощник*\n\n"
    "🔹 *Виртуальные номера* — быстрое получение номеров для Telegram и других сервисов\n\n"
    "🔹 */buystars* — отправка Telegram Stars и подарков Premium за TON\n\n"
    "🔹 *Кошелёк* — управление балансом TON: пополнение, история и оплата\n\n"
    "🔹 *Рефералы* — получайте 0.02 TON за активных друзей\n\n"
    "🔹 */ai* — умный AI-чат: ответы, помощь, генерация текста\n\n"
    "🔹 */hosting* — загрузка сайтов в .zip и автоматический хостинг в интернет\n\n"
    "🔹 */discount* — проверка NFT и активация 5% скидки на все покупки\n\n"
    "💡 Все функции доступны в меню. Нажмите /start для начала."
)

    else:
       info_text = (
    "🤖 *Arion_Dbot — all-in-one assistant*\n\n"
    "🔹 *Virtual Numbers* — instantly get numbers for Telegram & other services\n\n"
    "🔹 */buystars* — send Telegram Stars and gift Premium with TON\n\n"
    "🔹 *Wallet* — manage TON balance: top up, view history, and pay\n\n"
    "🔹 *Referrals* — earn 0.02 TON for each active invite\n\n"
    "🔹 */ai* — smart AI chat: answers, help, and text generation\n\n"
    "🔹 */hosting* — upload zipped websites and auto-host on the internet \n\n"
    "🔹 */discount* — verify NFT ownership to activate a 5% discount\n\n"
    "💡 All features are in the menu. Tap /start to begin."
)

    bot.send_message(msg.chat.id, info_text, parse_mode="Markdown")


# --- /buystars сразу показывает меню Telegram Services → Buy Stars / Buy Premium ---
@bot.message_handler(commands=["buystars"])
def cmd_buystars(msg):
    uid  = str(msg.from_user.id)
    lang = get_lang(uid)
    title = "✨ *Telegram Services*" if lang=="en" else "✨ *Сервисы Telegram*"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("⭐ Buy Stars"   if lang=="en" else "⭐ Купить звёзды",   callback_data="buy_stars"),
        InlineKeyboardButton("🎁 Buy Premium" if lang=="en" else "🎁 Купить премиум", callback_data="buy_premium"),
        BTN_CANCEL
    )
    bot.send_message(msg.chat.id, title, reply_markup=kb)


# ─── NFT Verification & 5% Discount Section ─────────────────────────────────

import time
import uuid
import threading
import logging
import requests

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# === Constants ===
DEPOSIT_ADDRESS          = "UQBRiESLIYaCIL6q9s9frfp3ZGz2Yp29FBycV0GIRZdeY9zP"
TONCENTER_BASE_URL       = "https://toncenter.com"
TONCENTER_API_KEY        = ""
TONAPI_BASE_URL          = "https://tonapi.io"
NFT_API_KEY              = ""
NFT_COLLECTION_ADDRESS   = "0:28f760d832893182129cabe0a40864a4fcc817639168d523d6db4824bd997be6"
INSTR_IMG_URL            = "https://raw.githubusercontent.com/qnexst/404token/main/nft.jpg"

# === In-memory stores ===
pending_discount_memos   = {}  # memo -> user_id
last_discount_lts        = {}  # memo -> last logical time

# === Logging ===
logging.basicConfig(level=logging.INFO)

# === Helpers ===
def decode_memo(hex_or_plain: str) -> str:
    try:
        return bytes.fromhex(hex_or_plain).decode("utf-8")
    except Exception:
        return hex_or_plain

def has_nft_collection(account_address: str) -> bool:
    """Check via TonAPI if the given account holds at least one NFT from the target collection."""
    try:
        resp = requests.get(
            f"{TONAPI_BASE_URL}/v2/accounts/{account_address}/nfts",
            headers={"x-api-key": NFT_API_KEY},
            timeout=10
        ).json()
    except Exception as e:
        logging.error(f"TonAPI request failed: {e}")
        return False

    nft_items = resp.get("nft_items") or resp.get("result", {}).get("nfts")
    if not isinstance(nft_items, list):
        return False

    target = NFT_COLLECTION_ADDRESS.lower()
    for item in nft_items:
        if item.get("collection", {}).get("address", "").lower() == target:
            return True
    return False

# === Polling Thread for Both Top-Up & Discount ===
def poll_deposits():
    while True:
        try:
            data = requests.get(
                f"{TONCENTER_BASE_URL}/api/v2/getTransactions",
                params={
                    "address":  DEPOSIT_ADDRESS,
                    "limit":    50,
                    "archival": "true",
                    "api_key":  TONCENTER_API_KEY
                },
                timeout=10
            ).json()

            if not data.get("ok"):
                time.sleep(20)
                continue

            for tx in data["result"]:
                lt   = int(tx["transaction_id"]["lt"])
                memo = decode_memo(tx["in_msg"].get("message", ""))
                source = tx["in_msg"].get("source", "unknown")

                # --- Discount Verification Handling ---
                if memo in pending_discount_memos and lt > last_discount_lts.get(memo, 0):
                    last_discount_lts[memo] = lt
                    uid = pending_discount_memos.pop(memo)

                    # Check NFT and update database
                    has_nft = source != "unknown" and has_nft_collection(source)
                    db.child("users").child(str(uid)).update({"has_nft": has_nft})

                    # Prepare response
                    if has_nft:
                        resp_text = (
                            "🎉 <b>NFT Verified!</b>\n\n"
                            "Congratulations—you hold an NFT from the collection.\n"
                            "Your 5% discount is now active on all services!"
                        )
                    else:
                        resp_text = (
                            "❌ <b>NFT Not Found</b>\n\n"
                            "We couldn't detect the NFT in your wallet.\n"
                            "No discount will be applied."
                        )

                    # Send confirmation
                    kb = InlineKeyboardMarkup().add(
                        InlineKeyboardButton("💼 Go to Wallet", callback_data="wallet")
                    )
                    bot.send_message(
                        int(uid),
                        resp_text,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        reply_markup=kb
                    )

        except Exception as e:
            logging.error(f"Deposit polling error: {e}")

        time.sleep(5)

# Start the polling thread
threading.Thread(target=poll_deposits, daemon=True).start()

# === /discount Command & Menu ===
@bot.message_handler(commands=['discount'])
def cmd_discount(msg):
    uid  = str(msg.from_user.id)
    lang = get_lang(uid)

    if lang == "en":
        title = (
            "🎉 <b>NFT Holder Discount</b> 🎉\n\n"
            "Get 5% off all services! Verify your NFT to activate the discount.\n"
            "Click \"Next\" for instructions."
        )
        btn_next = "Next ➡️"
        btn_cancel = "❌ Cancel"
    else:
        title = (
            "🎉 <b>Скидка для держателей NFT</b> 🎉\n\n"
            "Получите 5% скидку на все услуги! Подтвердите владение NFT.\n"
            "Нажмите «Далее» для инструкций."
        )
        btn_next = "Далее ➡️"
        btn_cancel = "❌ Отмена"

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton(btn_next, callback_data="discount_next"),
        InlineKeyboardButton(btn_cancel, callback_data="start_over")
    )
    bot.send_message(msg.chat.id, title, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(lambda c: c.data in ["discount_next", "discount_back"])
def cb_discount(c):
    bot.answer_callback_query(c.id)
    uid  = str(c.from_user.id)
    lang = get_lang(uid)

    if c.data == "discount_next":
        # Generate memo and save
        memo = uuid.uuid4().hex
        pending_discount_memos[memo] = uid

        if lang == "en":
            caption = (
                "❗ <b>Discount Verification</b>\n\n"
                "Send any amount of TON with the memo below to prove NFT ownership:\n\n"
                f"1️⃣ Address: <code>{DEPOSIT_ADDRESS}</code>\n"
                f"2️⃣ Memo:    <code>{memo}</code>\n\n"
                "<i>Link active for 20 minutes.</i>"
            )
            btn_back = "⬅️ Back"
        else:
            caption = (
                "❗ <b>Проверка для скидки</b>\n\n"
                "Отправьте любую сумму TON с memo ниже, чтобы подтвердить NFT:\n\n"
                f"1️⃣ Адрес: <code>{DEPOSIT_ADDRESS}</code>\n"
                f"2️⃣ Memo:   <code>{memo}</code>\n\n"
                "<i>Ссылка активна 20 минут.</i>"
            )
            btn_back = "⬅️ Назад"

        btn_pay = InlineKeyboardButton("💸 Open Ton Keeper", url=f"ton://transfer/{DEPOSIT_ADDRESS}?text={memo}")
        btn_cancel = InlineKeyboardButton(btn_back, callback_data="discount_back")
        kb2 = InlineKeyboardMarkup().add(btn_pay).add(btn_cancel)

        bot.send_photo(c.message.chat.id, INSTR_IMG_URL, caption=caption, parse_mode="HTML", reply_markup=kb2)

    else:  # c.data == "discount_back"
        # Go back to initial discount menu
        cmd_discount(c.message)

# --------------------------------------------------------------------------- #
#                              Admin Broadcast                                #
# --------------------------------------------------------------------------- #
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, Message
)

# временное хранилище «черновиков» постов: admin_uid → {"msg":Message, "preview_id":int}
pending_posts: dict[str, dict] = {}

def is_admin(uid: str) -> bool:
    """Проверка, является ли пользователь админом."""
    return db.child("users").child(uid).child("is_admin").get().val() is True

# ── /post ────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=['post'])
def cmd_post(message: Message):
    uid = str(message.from_user.id)
    if not is_admin(uid):
        return  # игнорируем, если не админ

    # просим отправить контент
    txt = "✏️ Отправьте пост (текст / фото / видео и т.д.)."
    ask = bot.send_message(uid, txt)
    bot.register_next_step_handler(ask, _capture_post)


def _capture_post(msg: Message):
    """Сохраняем пост и показываем предпросмотр с кнопками."""
    uid = str(msg.from_user.id)
    if not is_admin(uid):
        return

    # сохраняем сообщение-оригинал
    pending_posts[uid] = {"msg": msg}

    # клавиатура подтверждения
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data="post_send"),
        InlineKeyboardButton("❌ Отмена",       callback_data="post_cancel")
    )

    # показываем предпросмотр:
    if msg.content_type == "text":
        prev = bot.send_message(uid, msg.text, reply_markup=kb)
    elif msg.content_type == "photo":
        file_id = msg.photo[-1].file_id
        prev = bot.send_photo(uid, file_id, caption=msg.caption or "", reply_markup=kb)
    elif msg.content_type == "video":
        prev = bot.send_video(uid, msg.video.file_id,
                              caption=msg.caption or "", reply_markup=kb)
    else:
        prev = bot.send_message(uid, "⚠️ Тип сообщения не поддерживается.", reply_markup=kb)

    pending_posts[uid]["preview_id"] = prev.message_id

# ── обработка Confirm / Cancel ───────────────────────────────────────────────
@bot.callback_query_handler(lambda c: c.data in ["post_send", "post_cancel"])
def cb_post_confirm(c):
    bot.answer_callback_query(c.id)
    uid = str(c.from_user.id)
    draft = pending_posts.get(uid)
    if not draft:
        return

    # отмена
    if c.data == "post_cancel":
        try:
            bot.delete_message(uid, draft["preview_id"])
        except Exception:
            pass
        pending_posts.pop(uid, None)
        bot.send_message(uid, "🚫 Отправка отменена.")
        return

    # подтверждено → рассылаем
    src_msg: Message = draft["msg"]
    sent_cnt = 0

    # получаем всех пользователей
    users = db.child("users").get().val() or {}
    for user_uid, udata in users.items():
        try:
            # username может отсутствовать
            uname = udata.get("username") or udata.get("first_name", "user")
            mention = f"@{uname}"

            if src_msg.content_type == "text":
                text = src_msg.text.replace("@user", mention)
                bot.send_message(user_uid, text)
            elif src_msg.content_type == "photo":
                file_id = src_msg.photo[-1].file_id
                caption = (src_msg.caption or "").replace("@user", mention)
                bot.send_photo(user_uid, file_id, caption=caption)
            elif src_msg.content_type == "video":
                caption = (src_msg.caption or "").replace("@user", mention)
                bot.send_video(user_uid, src_msg.video.file_id, caption=caption)
            else:
                continue  # пропускаем неподдерживаемые типы

            sent_cnt += 1
            # ► необязательная микро-задержка, чтобы не словить flood-limit
            time.sleep(0.05)
        except Exception as e:
            logging.error(f"[Broadcast] cannot send to {user_uid}: {e}")

    # итог админу
    bot.edit_message_reply_markup(uid, draft["preview_id"], reply_markup=None)
    bot.send_message(uid, f"✅ Пост доставлен {sent_cnt} пользователям.")

    pending_posts.pop(uid, None)
# === Hosting Section ===
import os
import re
import zipfile
import tempfile
import shutil
import threading
import time
import requests
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.apihelper import ApiTelegramException
from github import Github, GithubException

# — Configuration —
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "YOUR_GITHUB_TOKEN")
GITHUB_USER  = "Arion-dbot"
GH_API_BASE  = "https://api.github.com"
HOST_PRICE   = 0.5   # TON per year

gh = Github(GITHUB_TOKEN)
gh_user = gh.get_user()

# — In-memory state —
awaiting_site_name = {}  # uid → None (awaiting name) or site_name
awaiting_zip       = {}  # uid → True when awaiting ZIP

# — Firebase helpers —  
def has_active_subscription(uid):
    sub = db.child("hosting_subs").child(uid).get().val() or {}
    return sub.get("expires", 0) > time.time()

def record_subscription(uid):
    now     = time.time()
    expires = now + 365*24*3600
    db.child("hosting_subs").child(uid).set({
        "start":     now,
        "expires":   expires,
        "site_name": None
    })
    return expires

# — Expiry thread —  
def schedule_expiry_check():
    while True:
        subs = db.child("hosting_subs").get().val() or {}
        now  = time.time()
        for uid, info in subs.items():
            if info.get("expires", 0) <= now:
                site = info.get("site_name")
                if site:
                    try: gh_user.get_repo(site).delete()
                    except: pass
                db.child("hosting_subs").child(uid).remove()
        time.sleep(24*3600)

threading.Thread(target=schedule_expiry_check, daemon=True).start()


# — /hosting command —  
@bot.message_handler(commands=['hosting'])
def cmd_hosting(msg):
    uid = str(msg.from_user.id)
    if not has_active_subscription(uid):
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(
            f"💳 Купить план — {HOST_PRICE} TON/год",
            callback_data="hosting_buy_plan"
        ))
        bot.send_message(
            msg.chat.id,
            f"🛠 Чтобы хостить сайт, купите годовой план за {HOST_PRICE} TON.",
            reply_markup=kb
        )
    else:
        # меню для подписанных
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("➕ Новый сайт",       callback_data="hosting_new_site"),
            InlineKeyboardButton("📋 Мои сайты",        callback_data="hosting_my_sites"),
        )
        kb.add(
            InlineKeyboardButton("💳 Мой план",         callback_data="hosting_status"),
            InlineKeyboardButton("🔔 Продлить план",    callback_data="hosting_renew")
        )
        kb.add(
            InlineKeyboardButton("⚙️ Настройки",        callback_data="hosting_settings")
        )
        bot.send_message(
            msg.chat.id,
            "🏠 *Меню хостинга*",
            parse_mode="Markdown",
            reply_markup=kb
        )


# — Купить план —  
@bot.callback_query_handler(lambda c: c.data=="hosting_buy_plan")
def cb_hosting_buy_plan(c):
    uid = str(c.from_user.id)
    bot.answer_callback_query(c.id)
    bal = fetch_balance(uid)
    if bal < HOST_PRICE:
        return bot.send_message(c.message.chat.id, t(uid, "no_balance"))
    save_balance(uid, bal - HOST_PRICE)
    expires = record_subscription(uid)
    bot.send_message(
        c.message.chat.id,
        f"✅ План активирован до {datetime.fromtimestamp(expires):%Y-%m-%d}.\n"
        "Отправьте /hosting, чтобы настроить сайт."
    )


# — Новый сайт —  
@bot.callback_query_handler(lambda c: c.data=="hosting_new_site")
def cb_hosting_new_site(c):
    uid = str(c.from_user.id)
    bot.answer_callback_query(c.id)
    awaiting_site_name[uid] = None
    bot.send_message(
        c.message.chat.id,
        "🌐 *Введите имя сайта* (1–50 символов, `a–z0-9-`):",
        parse_mode="Markdown"
    )


# — Ввод имени сайта —  
def is_waiting_name(msg):
    uid = str(msg.from_user.id)
    return uid in awaiting_site_name and awaiting_site_name[uid] is None

@bot.message_handler(func=is_waiting_name)
def process_site_name(msg):
    uid  = str(msg.from_user.id)
    name = msg.text.strip().lower()
    # валидация
    if not re.fullmatch(r'[a-z0-9-]{1,50}', name):
        return bot.send_message(
            msg.chat.id,
            "❌ Неверное имя. Используйте 1–50 символов: `a–z0-9-`. Попробуйте снова:",
            parse_mode="Markdown"
        )
    # проверка занятости
    try:
        gh_user.get_repo(name)
        return bot.send_message(
            msg.chat.id,
            "❌ Это имя уже занято. Выберите другое:",
            parse_mode="Markdown"
        )
    except GithubException:
        pass

    awaiting_site_name[uid] = name
    awaiting_zip[uid] = True
    bot.send_message(
        msg.chat.id,
        f"✅ Имя сайта `{name}` установлено.\n"
        "Пришлите ZIP с сайтом (с `index.html`):",
        parse_mode="Markdown"
    )


# — Загрузка ZIP —  
def is_waiting_zip(msg):
    uid = str(msg.from_user.id)
    return uid in awaiting_zip and awaiting_zip[uid] and msg.content_type=='document'

@bot.message_handler(func=is_waiting_zip, content_types=['document'])
def process_hosting_zip(msg):
    uid       = str(msg.from_user.id)
    site_name = awaiting_site_name.get(uid)
    lang      = get_lang(uid)

    # скачиваем, проверяем размер
    try:
        info = bot.get_file(msg.document.file_id)
        data = bot.download_file(info.file_path)
    except ApiTelegramException as e:
        if "file is too big" in str(e).lower():
            text = ("❌ Файл слишком большой (макс 50 МБ). Уменьшите размер."
                    if lang=="ru" else
                    "❌ Your file is too large (max 50 MB). Please reduce size.")
            return bot.send_message(msg.chat.id, text)
        raise

    # распаковываем
    workdir  = tempfile.mkdtemp()
    zip_path = os.path.join(workdir, msg.document.file_name)
    with open(zip_path,'wb') as f: f.write(data)
    with zipfile.ZipFile(zip_path,'r') as z: z.extractall(workdir)

    # ищем index.html
    publish_root = None
    for root,_,files in os.walk(workdir):
        if 'index.html' in files:
            publish_root = root; break
    if not publish_root:
        shutil.rmtree(workdir)
        awaiting_site_name.pop(uid); awaiting_zip.pop(uid)
        msg_text = ("❌ В ZIP нет `index.html`. Перезапустите /hosting."
                    if lang=="ru" else
                    "❌ No `index.html` found. Restart with /hosting.")
        return bot.send_message(msg.chat.id, msg_text)

    # промоут вложенную папку
    if publish_root!=workdir:
        wd2 = tempfile.mkdtemp()
        for fn in os.listdir(publish_root):
            shutil.move(os.path.join(publish_root,fn), wd2)
        shutil.rmtree(workdir); workdir = wd2

    bot.send_message(
        msg.chat.id,
        ("⏳ Загружаю и деплою… может занять 1–5 мин." if lang=="ru"
         else "⏳ Uploading & deploying… may take 1–5 min.")
    )

    # создаём или очищаем репо
    try:
        repo = gh_user.get_repo(site_name)
        for item in repo.get_contents("",ref="main"):
            repo.delete_file(item.path, f"Clear {item.path}", item.sha, branch="main")
    except GithubException:
        repo = gh_user.create_repo(
            name=site_name, private=False,
            homepage=f"https://{GITHUB_USER}.github.io/{site_name}"
        )

    # пушим файлы
    for root,_,files in os.walk(workdir):
        for fn in files:
            full = os.path.join(root,fn)
            rel  = os.path.relpath(full,workdir).replace("\\","/")
            with open(full,'rb') as f: content=f.read()
            try:
                existing = repo.get_contents(rel,ref="main")
                repo.update_file(rel,f"Update {rel}",content,existing.sha,branch="main")
            except GithubException:
                repo.create_file(rel,f"Add {rel}",content,branch="main")

    # .nojekyll
    try: repo.get_contents(".nojekyll",ref="main")
    except: repo.create_file(".nojekyll","Disable Jekyll","",branch="main")

    # включаем Pages
    requests.post(
        f"{GH_API_BASE}/repos/{GITHUB_USER}/{site_name}/pages",
        json={"source":{"branch":"main","path":"/"}},
        headers={"Authorization":f"token {GITHUB_TOKEN}"}
    )

    # сохраняем site_name
    db.child("hosting_subs").child(uid).update({"site_name":site_name})

    shutil.rmtree(workdir)
    awaiting_zip.pop(uid)

    # меню после деплоя
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📋 Мои сайты",       callback_data="hosting_my_sites"),
        InlineKeyboardButton("🔄 Обновить сайт",   callback_data="hosting_update_site"),
    )
    kb.add(
        InlineKeyboardButton("🗑 Удалить сайт",    callback_data="hosting_delete_site"),
        InlineKeyboardButton("💳 Мой план",        callback_data="hosting_status"),
    )
    kb.add(InlineKeyboardButton("🔔 Продлить план",callback_data="hosting_renew"))

    pages_url = f"https://{GITHUB_USER}.github.io/{site_name}/"
    msg_text = (f"✅ Сайт *{site_name}* в очереди:\n{pages_url}\n"
                "⚠️ Публикация может занять 1–5 мин.")
    bot.send_message(msg.chat.id, msg_text, parse_mode="Markdown", reply_markup=kb)


# — Настройки и остальные кнопки —  
@bot.callback_query_handler(lambda c: c.data=="hosting_my_sites")
def cb_my_sites(c):
    uid = str(c.from_user.id)
    sub = db.child("hosting_subs").child(uid).get().val() or {}
    site = sub.get("site_name")
    if not site:
        text = "У вас нет сайтов." if get_lang(uid)=="ru" else "You have no sites."
    else:
        url = f"https://{GITHUB_USER}.github.io/{site}/"
        text = f"🖥 Ваш сайт: `{site}`\n🔗 {url}" if get_lang(uid)=="ru" else f"🖥 Your site: `{site}`\n🔗 {url}"
    bot.send_message(c.message.chat.id, text, parse_mode="Markdown")

@bot.callback_query_handler(lambda c: c.data=="hosting_update_site")
def cb_update_site(c):
    uid = str(c.from_user.id)
    if has_active_subscription(uid):
        awaiting_zip[uid] = True
        text = "📦 Пришлите новый ZIP для обновления." if get_lang(uid)=="ru" else "📦 Send new ZIP to update."
    else:
        text = "❌ План не активен. Купите через /hosting." if get_lang(uid)=="ru" else "❌ No active plan—buy via /hosting."
    bot.send_message(c.message.chat.id, text)

@bot.callback_query_handler(lambda c: c.data=="hosting_delete_site")
def cb_delete_site(c):
    uid = str(c.from_user.id)
    sub= db.child("hosting_subs").child(uid).get().val() or {}
    site=sub.get("site_name")
    if site:
        try: gh_user.get_repo(site).delete()
        except: pass
    db.child("hosting_subs").child(uid).remove()
    msg = f"🗑 Сайт `{site}` удалён." if get_lang(uid)=="ru" else f"🗑 Site `{site}` deleted."
    bot.send_message(c.message.chat.id, msg)

@bot.callback_query_handler(lambda c: c.data=="hosting_status")
def cb_status(c):
    uid = str(c.from_user.id)
    exp= db.child("hosting_subs").child(uid).get().val().get("expires",0)
    if exp>time.time():
        ts = datetime.fromtimestamp(exp).strftime('%Y-%m-%d')
        text = f"⏳ Действителен до: {ts}" if get_lang(uid)=="ru" else f"⏳ Expires on: {ts}"
    else:
        text = "❌ План истёк." if get_lang(uid)=="ru" else "❌ Plan expired."
    bot.send_message(c.message.chat.id, text)

@bot.callback_query_handler(lambda c: c.data=="hosting_renew")
def cb_renew(c):
    return cb_hosting_buy_plan(c)

# --------------------------------------------------------------------------- #
#                                  Run Loop                                   #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    threading.Thread(target=poll_deposits, daemon=True).start()
    bot.infinity_polling(skip_pending=True)
