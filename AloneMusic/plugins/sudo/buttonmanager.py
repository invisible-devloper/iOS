#
# Owner-only Custom Button Manager.
#
# /buttons                               show layout + help
# /addurl [row] Text | https://link      add URL button (row omitted = new row)
# /addmsg [row] Text | Message text      add callback button that replies with text
# /delbutton <row> <col>                 delete a button
# /moverow <from> <to>                   reorder rows
# /movebutton <row> <col> <to_row> [to_col]   move a button (to_row = rows+1 makes a new row)
# /clearbuttons                          remove all buttons

from html import escape
from urllib.parse import urlparse

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, Message

import config
from AloneMusic import app
from AloneMusic.utils.custombuttons import (
    CB_PREFIX,
    add_button,
    delete_button,
    get_layout,
    get_message,
    move_button,
    move_row,
    save_layout,
    to_keyboard,
)

OWNER = filters.user(config.OWNER_ID)

HELP = (
    "<b>Custom Button Manager</b>\n\n"
    "/addurl [row] Text | https://link\n"
    "/addmsg [row] Text | Message shown on click\n"
    "/delbutton row col\n"
    "/moverow from to\n"
    "/movebutton row col to_row [to_col]\n"
    "/clearbuttons\n\n"
    "Omit <code>row</code> to start a new row. Buttons appear on the private /start panel."
)


def _split_row(message: Message):
    """Parse '[row] a | b' from the command arguments. Returns (row, a, b) or None."""
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return None
    body = parts[1]
    row = None
    first, _, rest = body.partition(" ")
    if first.isdigit():
        row, body = int(first), rest
    if "|" not in body:
        return None
    left, right = body.split("|", 1)
    left, right = left.strip(), right.strip()
    if not left or not right:
        return None
    return row, left, right


def _ints(message: Message, minimum: int, maximum: int):
    args = message.command[1:]
    if not minimum <= len(args) <= maximum or not all(a.isdigit() for a in args):
        return None
    return [int(a) for a in args]


def _valid_url(url: str) -> bool:
    # Telegram rejects bad button URLs for the whole keyboard, which would break /start.
    if " " in url or len(url) > 512:
        return False
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        return "." in parsed.netloc and not parsed.netloc.startswith(".")
    return parsed.scheme == "tg" and bool(parsed.netloc)


async def _layout_text() -> str:
    rows = await get_layout()
    if not rows:
        return "No custom buttons yet."
    lines = []
    for i, row in enumerate(rows, 1):
        cells = [
            f"{j}. {'🔗' if b['type'] == 'url' else '💬'} {escape(b['text'])}"
            for j, b in enumerate(row, 1)
        ]
        lines.append(f"<b>Row {i}:</b> " + "  ".join(cells))
    return "\n".join(lines)


@app.on_message(filters.command("buttons") & filters.private & OWNER)
async def buttons_panel(_, message: Message):
    rows = await get_layout()
    await message.reply_text(
        f"{HELP}\n\n<b>Current layout:</b>\n{await _layout_text()}",
        reply_markup=InlineKeyboardMarkup(to_keyboard(rows)) if rows else None,
    )


@app.on_message(filters.command("addurl") & filters.private & OWNER)
async def add_url_button(_, message: Message):
    parsed = _split_row(message)
    if not parsed:
        return await message.reply_text("Usage: /addurl [row] Text | https://link")
    row, text, url = parsed
    if not _valid_url(url):
        return await message.reply_text(
            "Invalid URL. Use https://example.com/... or tg://..."
        )
    ok, err = await add_button("url", text[:64], url, row)
    await message.reply_text("URL button added." if ok else err)


@app.on_message(filters.command("addmsg") & filters.private & OWNER)
async def add_msg_button(_, message: Message):
    parsed = _split_row(message)
    if not parsed:
        return await message.reply_text("Usage: /addmsg [row] Text | Message text")
    row, text, content = parsed
    ok, err = await add_button("msg", text[:64], content[:4000], row)
    await message.reply_text("Message button added." if ok else err)


@app.on_message(filters.command("delbutton") & filters.private & OWNER)
async def del_button(_, message: Message):
    args = _ints(message, 2, 2)
    if not args:
        return await message.reply_text("Usage: /delbutton row col")
    removed = await delete_button(*args)
    await message.reply_text(
        f"Deleted “{removed['text']}”." if removed else "No button at that position."
    )


@app.on_message(filters.command("moverow") & filters.private & OWNER)
async def move_row_cmd(_, message: Message):
    args = _ints(message, 2, 2)
    if not args:
        return await message.reply_text("Usage: /moverow from to")
    ok = await move_row(*args)
    await message.reply_text("Row moved." if ok else "Invalid row numbers.")


@app.on_message(filters.command("movebutton") & filters.private & OWNER)
async def move_button_cmd(_, message: Message):
    args = _ints(message, 3, 4)
    if not args:
        return await message.reply_text("Usage: /movebutton row col to_row [to_col]")
    ok = await move_button(
        args[0], args[1], args[2], args[3] if len(args) == 4 else None
    )
    await message.reply_text(
        "Button moved." if ok else "Invalid position or target row full."
    )


@app.on_message(filters.command("clearbuttons") & filters.private & OWNER)
async def clear_buttons(_, message: Message):
    await save_layout([])
    await message.reply_text("All custom buttons removed.")


@app.on_callback_query(filters.regex(f"^{CB_PREFIX}"))
async def custom_button_click(_, query):
    content = await get_message(query.data[len(CB_PREFIX) :])
    if content is None:
        return await query.answer("This button no longer exists.", show_alert=True)
    if len(content) <= 200:
        return await query.answer(content, show_alert=True)
    await query.answer()
    await query.message.reply_text(content, parse_mode=ParseMode.DISABLED)
