#
# Owner-managed custom buttons: storage and keyboard rendering.
# Stored in the existing MongoDB (collection `custombuttons`), one layout document.

import uuid

from pyrogram.types import InlineKeyboardButton

from AloneMusic.core.mongo import mongodb

buttondb = mongodb.custombuttons
_LAYOUT_ID = "layout"
CB_PREFIX = "cbtn:"
MAX_PER_ROW = 8
MAX_BUTTONS = 40


async def get_layout() -> list:
    doc = await buttondb.find_one({"_id": _LAYOUT_ID})
    return doc.get("rows", []) if doc else []


async def save_layout(rows: list):
    rows = [r for r in rows if r]
    await buttondb.update_one(
        {"_id": _LAYOUT_ID}, {"$set": {"rows": rows}}, upsert=True
    )


def count_buttons(rows: list) -> int:
    return sum(len(r) for r in rows)


async def add_button(kind: str, text: str, value: str, row: int | None):
    """kind: 'url' or 'msg'. row is 1-based, or None for a new row.
    Returns (ok, error)."""
    rows = await get_layout()
    if count_buttons(rows) >= MAX_BUTTONS:
        return False, f"Limit of {MAX_BUTTONS} buttons reached."
    btn = {"id": uuid.uuid4().hex[:10], "type": kind, "text": text, "value": value}
    if row is None:
        rows.append([btn])
    else:
        if row < 1 or row > len(rows):
            return False, f"Row {row} does not exist (rows: {len(rows)})."
        if len(rows[row - 1]) >= MAX_PER_ROW:
            return False, f"Row {row} is full ({MAX_PER_ROW} max)."
        rows[row - 1].append(btn)
    await save_layout(rows)
    return True, None


async def delete_button(row: int, col: int):
    rows = await get_layout()
    if row < 1 or row > len(rows) or col < 1 or col > len(rows[row - 1]):
        return None
    removed = rows[row - 1].pop(col - 1)
    await save_layout(rows)
    return removed


async def move_row(src: int, dst: int) -> bool:
    rows = await get_layout()
    if not (1 <= src <= len(rows) and 1 <= dst <= len(rows)):
        return False
    rows.insert(dst - 1, rows.pop(src - 1))
    await save_layout(rows)
    return True


async def move_button(row: int, col: int, to_row: int, to_col: int | None) -> bool:
    """Move a button to another row (appended, or at to_col) or within its row."""
    rows = await get_layout()
    if row < 1 or row > len(rows) or col < 1 or col > len(rows[row - 1]):
        return False
    if to_row < 1 or to_row > len(rows) + 1:
        return False
    if to_row <= len(rows) and to_row != row and len(rows[to_row - 1]) >= MAX_PER_ROW:
        return False
    btn = rows[row - 1].pop(col - 1)
    if to_row == len(rows) + 1:
        rows.append([btn])
    else:
        target = rows[to_row - 1]
        idx = len(target) if to_col is None else max(0, min(to_col - 1, len(target)))
        target.insert(idx, btn)
    await save_layout(rows)
    return True


async def get_message(button_id: str):
    for row in await get_layout():
        for b in row:
            if b["id"] == button_id:
                return b["value"] if b["type"] == "msg" else None
    return None


def to_keyboard(rows: list) -> list:
    keyboard = []
    for row in rows:
        line = []
        for b in row:
            if b["type"] == "url":
                line.append(InlineKeyboardButton(text=b["text"], url=b["value"]))
            else:
                line.append(
                    InlineKeyboardButton(
                        text=b["text"], callback_data=f"{CB_PREFIX}{b['id']}"
                    )
                )
        if line:
            keyboard.append(line)
    return keyboard


async def get_custom_rows() -> list:
    """Keyboard rows for display; never raises (safe to call from /start)."""
    try:
        return to_keyboard(await get_layout())
    except Exception:
        return []
