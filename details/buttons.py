from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
start_but = [
    ["Ovozli🎙", "Yozma📝"],
    ["Hisobot📊"],
    ["Chiqish🔴"]
]

back_but = [
    ["Ortga🔙"]
]

edit_but = [
    [
        InlineKeyboardButton(
            "Adress ✏️",
            callback_data="edit_adress"
        )
    ],
    [
        InlineKeyboardButton(
            "Orientir ✏️",
            callback_data="edit_orientir"
        )
    ],
    [
        InlineKeyboardButton(
            "Kod ✏️",
            callback_data="edit_code"
        )
    ],
    [
        InlineKeyboardButton(
            "Oxirgi tashrif ✏️",
            callback_data="edit_pribel"
        )
    ],
    [
        InlineKeyboardButton(
            "Izoh ✏️",
            callback_data="edit_izoh"
        )
    ],
    [
        InlineKeyboardButton(
            "Ortga 🔙",
            callback_data="back"
        ),
        InlineKeyboardButton(
            "Tasdiqlash ✅",
            callback_data="confirm"
        )
    ]
]

edit_keyboard = InlineKeyboardMarkup(edit_but)