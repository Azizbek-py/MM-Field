import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import CellFormat, Color, format_cell_range
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from settings import BOT_TOKEN, GROUP_ID
from .buttons import *
from .messages import *
from .database.db import insert, get, upd
from .ai import stt, analyze_query2
import logging

logger = logging.getLogger(__name__)

FIELD_LABELS = {
    "adress": "Fillial manzilini yozing",
    "orent": "Orientir",
    "code": "Do'konning kodini kiriting",
    "pribel": "So'ngi tashrif",
    "coment": "Vaziyat yoki muammo haqida yozing",
}

FIELD_ORDER = ["adress", "orent", "code", "pribel", "coment"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key("1geDCrBLddyKxy2iwYjsjvmFC2Nb9_wRrBnsBglkcBbo").sheet1

async def log_deleter(user_id, keys, context):
    key_list = [keys] if isinstance(keys, str) else keys
    for key in key_list:
        for msg_id in list(context.user_data.get(key, [])):
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=msg_id)
            except Exception:
                pass
        context.user_data[key] = []

async def log_adder(type, context, msg_id):
    ids = msg_id if isinstance(msg_id, list) else [msg_id]
    for message_id in ids:
        context.user_data.setdefault(str(type), []).append(message_id)

async def clear_report_state(user_id, context):
    upd(
        table="users",
        data={
            "stage": "start",
            "report_type": None,
            "draft": {},
            "photos": [],
            "photo_len": 0,
            "voice_text": {},
            "edit_field": None,
            "field_index": 0,
        },
        user_id=user_id,
    )
    await log_deleter(user_id, ["messages", "start"], context)

async def send_start_menu(user_id, context):
    await log_deleter(user_id, ["messages", "start"], context)
    msg = await context.bot.send_message(
        chat_id=user_id,
        text=start_mes,
        reply_markup=ReplyKeyboardMarkup(keyboard=start_but, resize_keyboard=True),
    )
    await log_adder("messages", context, [msg.message_id])
    upd(table="users", data={"stage": "start"}, user_id=user_id)

async def send_confirmation(user_id, context, draft):
    draft = dict(draft or {})
    draft.setdefault("stand_code", "1")
    upd(table="users", data={"stage": "confirm_report", "draft": draft}, user_id=user_id)
    text_message = last_settings_mes.format(
        address=draft.get("adress", "-"),
        orientir=draft.get("orent", "-"),
        code=draft.get("code", "-"),
        pribel=draft.get("pribel", "-"),
        izoh=draft.get("coment", "-"),
    )
    await log_deleter(user_id, ["messages"], context)
    msg = await context.bot.send_message(
        chat_id=user_id,
        text=text_message,
        reply_markup=edit_keyboard,
        parse_mode=ParseMode.HTML,
    )
    await log_adder("messages", context, [msg.message_id])


def get_field_prompt(field_key, step_index=None):
    label = FIELD_LABELS.get(field_key, field_key)
    total = len(FIELD_ORDER)
    if step_index is not None:
        return f"{step_index}/{total}\n{label}"
    return label

async def send_stats(user_id, context):
    values = sheet.get_all_values()
    now = datetime.now()
    today = now.strftime("%d.%m.%Y")
    month = now.strftime("%m.%Y")
    today_count = 0
    month_count = 0
    for row in values:
        if len(row) > 0 and row[0]:
            if row[0] == today:
                today_count += 1
            if row[0].endswith(month):
                month_count += 1
    await log_deleter(user_id, ["messages"], context)
    msg = await context.bot.send_message(
        chat_id=user_id,
        text=stats_mes.format(today=today_count, month=month_count),
        reply_markup=ReplyKeyboardMarkup(keyboard=back_but, resize_keyboard=True),
    )
    await log_adder("messages", context, [msg.message_id])
    upd(table="users", data={"stage": "stats"}, user_id=user_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get(table="users", user_id=user_id)
    if user is None:
        insert(table="users", data={"user_id": user_id, "stage": "get_login", "logged_in": False}, user_id=user_id)
        await update.message.reply_text(text=login_mes)
        return
    if user.get("logged_in") is not True:
        upd(table="users", data={"stage": "get_login"}, user_id=user_id)
        await update.message.reply_text(text=login_mes)
        return
    await send_start_menu(user_id, context)

async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if value.lower() == "doxod_rent_base":
        try:
            with open("details/database/base.json", "rb") as file:
                await update.message.reply_document(document=file, filename="base.json", caption="base.json")
        except Exception:
            await update.message.reply_text("base.json topilmadi.")
        return

    user_id = update.effective_user.id
    user = get(table="users", user_id=user_id)
    if not user:
        return

    stage = user.get("stage")

    if stage == "get_login":
        upd(table="users", data={"login": value, "stage": "get_password"}, user_id=user_id)
        await log_deleter(user_id, ["messages"], context)
        msg = await update.message.reply_text(text=get_password_mes)
        await log_adder("messages", context, [update.message.message_id, msg.message_id])
        return

    if stage == "get_password":
        login = user.get("login")
        admins = get(table="admins")
        admin = next((item for item in admins if item.get("login") == login and str(item.get("parol")) == value), None)
        if admin:
            upd(table="users", data={"logged_in": True, "stage": "start"}, user_id=user_id)
            await log_deleter(user_id, ["messages"], context)
            await update.message.reply_text(text=start_mes, reply_markup=ReplyKeyboardMarkup(keyboard=start_but, resize_keyboard=True))
            return
        upd(table="users", data={"stage": "get_login"}, user_id=user_id)
        await log_deleter(user_id, ["messages"], context)
        msg = await update.message.reply_text(text=invalid_login_mes)
        await log_adder("messages", context, [update.message.message_id, msg.message_id])
        return

    if stage == "start":
        if value == "Ovozli🎙":
            upd(table="users", data={"stage": "voice_report", "photo_len": 0, "photos": [], "draft": {}}, user_id=user_id)
            await log_deleter(user_id, ["messages"], context)
            msg = await update.message.reply_text(text=send_photo_mes, reply_markup=ReplyKeyboardMarkup(keyboard=back_but, resize_keyboard=True))
            await log_adder("messages", context, [update.message.message_id, msg.message_id])
            return
        if value == "Yozma📝":
            upd(table="users", data={"stage": "text_report", "photo_len": 0, "photos": [], "draft": {}}, user_id=user_id)
            await log_deleter(user_id, ["messages"], context)
            msg = await update.message.reply_text(text=send_photo_mes, reply_markup=ReplyKeyboardMarkup(keyboard=back_but, resize_keyboard=True))
            await log_adder("messages", context, [update.message.message_id, msg.message_id])
            return
        if value == "Hisobot📊":
            await send_stats(user_id, context)
            return
        if value == "Chiqish🔴":
            upd(table="users", data={"logged_in": False, "stage": "get_login", "draft": {}}, user_id=user_id)
            await log_deleter(user_id, ["messages"], context)
            msg = await update.message.reply_text(text=login_mes)
            await log_adder("messages", context, [update.message.message_id, msg.message_id])
            return
        if value == "Ortga🔙":
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=update.message.message_id)
            except Exception:
                pass
            await send_start_menu(user_id, context)
            return

    if stage == "stats":
        if value == "Ortga🔙":
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=update.message.message_id)
            except Exception:
                pass
            await send_start_menu(user_id, context)
            return

    if stage in ["voice_report", "text_report"]:
        if value == "Ortga🔙":
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=update.message.message_id)
            except Exception:
                pass
            await clear_report_state(user_id, context)
            await send_start_menu(user_id, context)
            return

    if stage == "text_wait_field":
        if value == "Ortga🔙":
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=update.message.message_id)
            except Exception:
                pass
            await clear_report_state(user_id, context)
            await send_start_menu(user_id, context)
            return
        field = user.get("edit_field") or "adress"
        draft = user.get("draft") or {}
        draft[field] = value
        fields = FIELD_ORDER
        next_index = user.get("field_index", 0) + 1
        if next_index < len(fields):
            next_field = fields[next_index]
            upd(table="users", data={"draft": draft, "field_index": next_index, "edit_field": next_field, "stage": "text_wait_field"}, user_id=user_id)
            await log_deleter(user_id, ["messages"], context)
            msg = await update.message.reply_text(
                text=get_field_prompt(next_field, next_index + 1),
                reply_markup=ReplyKeyboardMarkup(keyboard=back_but, resize_keyboard=True),
            )
            await log_adder("messages", context, [update.message.message_id, msg.message_id])
            return
        upd(table="users", data={"draft": draft, "field_index": 0, "edit_field": None, "stage": "confirm_report"}, user_id=user_id)
        await send_confirmation(user_id, context, draft)
        return

    if stage == "editing_field":
        if value == "Ortga🔙":
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=update.message.message_id)
            except Exception:
                pass
            await log_deleter(user_id, ["messages"], context)
            await send_confirmation(user_id, context, user.get("draft") or {})
            return
        field = user.get("edit_field")
        draft = user.get("draft") or {}
        draft[field] = value
        upd(table="users", data={"draft": draft, "stage": "confirm_report"}, user_id=user_id)
        await log_deleter(user_id, ["messages"], context)
        await send_confirmation(user_id, context, draft)
        return

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get(table="users", user_id=user_id)
    if not user or user.get("logged_in") is not True:
        return

    stage = user.get("stage")
    if stage not in ["voice_report", "text_report"]:
        return

    photo_len = user.get("photo_len", 0)
    if photo_len >= 3:
        return

    photo_file_id = update.message.photo[-1].file_id
    photos = user.get("photos", [])
    photos.append(photo_file_id)
    upd(table="users", data={"photos": photos, "photo_len": photo_len + 1}, user_id=user_id)

    if photo_len + 1 < 3:
        await log_deleter(user_id, ["messages"], context)
        msg = await update.message.reply_text(text=f"Yana {3 - (photo_len + 1)} ta rasm yuboring...")
        await log_adder("messages", context, [update.message.message_id, msg.message_id])
        return

    if stage == "voice_report":
        upd(table="users", data={"stage": "voice_get_comment"}, user_id=user_id)
        await log_deleter(user_id, ["messages"], context)
        msg = await update.message.reply_text(text=voice_mes, reply_markup=ReplyKeyboardMarkup(keyboard=back_but, resize_keyboard=True))
        await log_adder("messages", context, [update.message.message_id, msg.message_id])
        return

    upd(table="users", data={"stage": "text_wait_field", "field_index": 0, "edit_field": "adress"}, user_id=user_id)
    await log_deleter(user_id, ["messages"], context)
    msg = await update.message.reply_text(
        text=get_field_prompt("adress", 1),
        reply_markup=ReplyKeyboardMarkup(keyboard=back_but, resize_keyboard=True),
    )
    await log_adder("messages", context, [update.message.message_id, msg.message_id])

async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get(table="users", user_id=user_id)
    if not user or user.get("logged_in") is not True:
        return
    if user.get("stage") != "voice_get_comment":
        return

    await log_adder("messages", context, [update.message.message_id])
    wait_msg = await update.message.reply_text(
        text="Ovozli xabar qabul qilindi. Ma'lumotlar tahlil qilinmoqda. Iltimos, kuting...",
        reply_markup=ReplyKeyboardMarkup(keyboard=back_but, resize_keyboard=True),
    )
    await log_adder("messages", context, [wait_msg.message_id])

    file_id = update.message.voice.file_id
    try:
        transcription = stt(file_id)
        if not transcription or (isinstance(transcription, str) and (
            transcription.lower().startswith("error") or
            "request failed" in transcription.lower() or
            "timed out" in transcription.lower()
        )):
            await update.message.reply_text(
                "Ovozli xabarni tahlil qilishda xizmatda muammo yuz berdi. Asosiy menyuga qaytmoqda. Iltimos, keyinroq urinib ko'ring."
            )
            await clear_report_state(user_id, context)
            await send_start_menu(user_id, context)
            return
        result = analyze_query2(transcription)
    except Exception:
        logger.exception("AI/STT failure in voice handler")
        await update.message.reply_text(
            "Xizmatga ulanishda xatolik yuz berdi. Asosiy menyuga qaytmoqda. Iltimos, keyinroq urinib ko'ring."
        )
        await clear_report_state(user_id, context)
        await send_start_menu(user_id, context)
        return
    raw = {
        "adress": result.get("adress", "-") if isinstance(result, dict) else "-",
        "orent": result.get("orent", "-") if isinstance(result, dict) else "-",
        "code": result.get("code", "-") if isinstance(result, dict) else "-",
        "pribel": result.get("pribel", "-") if isinstance(result, dict) else "-",
        "coment": result.get("coment", "-") if isinstance(result, dict) else "-",
    }
    raw.setdefault("stand_code", "1")
    upd(table="users", data={"voice_text": raw, "draft": raw, "stage": "confirm_report"}, user_id=user_id)
    await log_deleter(user_id, ["messages"], context)
    await send_confirmation(user_id, context, raw)

async def callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return

    user_id = query.from_user.id
    user = get(table="users", user_id=user_id)
    if not user:
        return

    await query.answer()
    action = query.data

    if action == "back":
        try:
            await query.message.delete()
        except Exception:
            pass
        await clear_report_state(user_id, context)
        await send_start_menu(user_id, context)
        return

    if action == "confirm":
        draft = dict(user.get("draft") or user.get("voice_text") or {})
        draft.setdefault("stand_code", "1")
        admin = get_admin_profile(user.get("login"))

        await query.message.edit_text("Ma'lumotlar Excelga yozilmoqda. Iltimos, kuting...")
        try:
            save_data(
                address=draft.get("adress", "-"),
                orientir=draft.get("orent", "-"),
                client_code=draft.get("code", "-"),
                last_visit=draft.get("pribel", "-"),
                stand_code=draft.get("stand_code", "1"),
                comment=draft.get("coment", "-"),
                conclusion=draft.get("coment", "-"),
                analyst_name=admin.get("name", user.get("login", "-")),
                analyst_phone=admin.get("phone", "-"),
                media_ids=user.get("photos", []),
            )
            await post_to_group(context, user.get("photos", []), draft, admin)
        except Exception:
            logger.exception("Failed to save or post report on confirm")
            await query.message.reply_text(
                "Hisobotni saqlash yoki guruhga yuborishda muammo yuz berdi. Asosiy menyuga qaytmoqda. Iltimos, keyinroq urinib ko'ring."
            )
        finally:
            await clear_report_state(user_id, context)
            await send_start_menu(user_id, context)
        return

    if action.startswith("edit_"):
        field = action.replace("edit_", "")
        field_map = {
            "adress": "adress",
            "orientir": "orent",
            "code": "code",
            "pribel": "pribel",
            "izoh": "coment",
        }
        field_key = field_map.get(field, field)
        if field_key not in FIELD_LABELS:
            return
        step_index = FIELD_ORDER.index(field_key) + 1
        upd(table="users", data={"stage": "editing_field", "edit_field": field_key}, user_id=user_id)
        await log_deleter(user_id, ["messages"], context)
        msg = await query.message.reply_text(
            text=get_field_prompt(field_key, step_index),
            reply_markup=ReplyKeyboardMarkup(keyboard=back_but, resize_keyboard=True),
        )
        await log_adder("messages", context, [query.message.message_id, msg.message_id])
        return


def get_admin_profile(login):
    admins = get(table="admins") or []
    for item in admins:
        if item.get("login") == login:
            return item
    return {"name": login, "phone": "-"}


def save_data(address, orientir, client_code, last_visit, stand_code, comment, conclusion, analyst_name, analyst_phone, media_ids=None):
    now = datetime.now()
    photos = media_ids or []
    photo_1 = photos[0] if len(photos) > 0 else ""
    photo_2 = photos[1] if len(photos) > 1 else ""
    photo_3 = photos[2] if len(photos) > 2 else ""

    row = [
        now.strftime("%d.%m.%Y"),
        now.strftime("%H:%M"),
        address,
        orientir,
        client_code,
        last_visit,
        stand_code,
        comment,
        conclusion,
        photo_1,
        photo_2,
        photo_3,
        analyst_name,
        analyst_phone,
        "",
        "",
    ]
    sheet.append_row(row, value_input_option="USER_ENTERED")
    last_row = len(sheet.get_all_values())
    red_format = CellFormat(backgroundColor=Color(1, 0, 0))
    format_cell_range(sheet, f"O{last_row}", red_format)


async def post_to_group(context, photos, draft, admin):
    if not photos:
        return
    caption = (
        f"<b>Bugungi sana:</b> {datetime.now().strftime('%d.%m.%Y')}\n"
        f"<b>Vaqt:</b> {datetime.now().strftime('%H:%M')}\n\n"
        f"1. <b>Адрес:</b> {draft.get('adress', '-')}\n"
        f"2. <b>Код клиента:</b> {draft.get('code', '-')}\n"
        f"3. <b>Ориентир:</b> {draft.get('orent', '-')}\n"
        f"4. <b>Последний прибытия торгового агента:</b> {draft.get('pribel', '-')}\n"
        f"5. <b>Код стенда:</b> {draft.get('stand_code', '1')}\n"
        f"6. <b>Комментария от клиента:</b> {draft.get('coment', '-')}\n"
        f"7. <b>Заключение:</b> {draft.get('coment', '-')}\n"
        f"8. <b>Аналитик:</b> {admin.get('name', '-')}\n"
        f"9. <b>Телефон:</b> {admin.get('phone', '-')}"
    )
    media = []
    for index, photo_id in enumerate(photos[:10]):
        media.append(
            InputMediaPhoto(
                media=photo_id,
                caption=caption if index == 0 else "",
                parse_mode=ParseMode.HTML,
            )
        )
    if media:
        await context.bot.send_media_group(chat_id=GROUP_ID, media=media)
