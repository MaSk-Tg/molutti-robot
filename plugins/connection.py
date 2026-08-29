from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.connections_mdb import (
    add_connection,
    all_connections,
    if_active,
    delete_connection,
)
from info import ADMINS
import logging
import re

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


def _chat_type(message):
    """Return Pyrogram chat type as a plain lowercase string.

    Pyrogram/Pyrofork may expose Chat.type as an enum (for example
    ChatType.PRIVATE). Using .value when available avoids comparing an
    enum's string representation with plain strings.
    """
    chat = getattr(message, "chat", None)
    value = getattr(getattr(chat, "type", None), "value", None)
    if value is None:
        value = str(getattr(chat, "type", ""))
    return str(value).lower().split(".")[-1]


def _extract_group_id(message):
    """Extract a negative Telegram group/supergroup ID from /connect args."""
    command = getattr(message, "command", None) or []

    # In Pyrogram this is normally: ['/connect', '-1001234567890'].
    for item in command[1:]:
        token = str(item).strip()
        if re.fullmatch(r"-\d{5,}", token):
            try:
                value = int(token)
            except ValueError:
                continue
            if value < 0:
                return value

    # Fallback for unusual clients/raw command parsing.
    raw_text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
    match = re.search(r"(?<!\d)-\d{5,}(?!\d)", raw_text)
    if match:
        try:
            value = int(match.group(0))
            if value < 0:
                return value
        except ValueError:
            pass

    return None


@Client.on_message(
    (filters.private | filters.group)
    & filters.command("connect")
    & filters.user(ADMINS)
)
async def addconnection(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply_text(
            "You are anonymous admin. Use /connect <group_id> in PM"
        )

    chat_type = _chat_type(message)

    # PM: /connect -1001234567890
    if chat_type == "private":
        group_id = _extract_group_id(message)
        if group_id is None:
            return await message.reply_text(
                "<b>❌ Enter the Group ID correctly.</b>\n\n"
                "Use:\n<code>/connect -1001234567890</code>\n\n"
                "The bot must already be present in that group, or run "
                "<code>/connect</code> directly inside the group.",
                quote=True,
            )

    # Group/supergroup: /connect (no ID needed)
    elif chat_type in ("group", "supergroup"):
        group_id = message.chat.id

    else:
        return await message.reply_text(
            "<b>❌ Unable to determine the group ID.</b>\n\n"
            "Use <code>/connect -1001234567890</code> in PM or run "
            "<code>/connect</code> inside the group.",
            quote=True,
        )

    try:
        # Verify the requesting user has access to the target group.
        st = await client.get_chat_member(int(group_id), userid)
        if st.status not in ("administrator", "creator") and userid not in ADMINS:
            return await message.reply_text(
                "You should be an admin in the given group!",
                quote=True,
            )
    except Exception as e:
        logger.exception("Unable to verify requesting user for group %s: %s", group_id, e)
        return await message.reply_text(
            "❌ Invalid Group ID!\n\n"
            "If the ID is correct, make sure the bot and you are present in the group.",
            quote=True,
        )

    try:
        # The bot must be present in the target group and be an administrator.
        bot_member = await client.get_chat_member(int(group_id), "me")
        if bot_member.status not in ("administrator", "creator"):
            return await message.reply_text(
                "❌ Please add me as an admin in the group first.",
                quote=True,
            )

        chat = await client.get_chat(int(group_id))
        title = chat.title or "this group"

        connected = await add_connection(str(group_id), str(userid))
        if not connected:
            return await message.reply_text(
                "You're already connected to this chat!",
                quote=True,
            )

        await message.reply_text(
            f"<b>✅ Successfully connected to {title}</b>\n"
            "Now manage your group from my PM!",
            quote=True,
        )

        # If /connect was run in the group, also send confirmation to PM.
        if chat_type in ("group", "supergroup"):
            try:
                await client.send_message(
                    userid,
                    f"<b>✅ Connected to {title}!</b>",
                )
            except Exception as e:
                logger.exception("Unable to send PM confirmation: %s", e)

    except Exception as e:
        logger.exception("Connection error for group %s: %s", group_id, e)
        await message.reply_text(
            "Some error occurred! Try again later.",
            quote=True,
        )


@Client.on_message(
    (filters.private | filters.group)
    & filters.command("disconnect")
    & filters.user(ADMINS)
)
async def deleteconnection(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply_text(
            f"You are anonymous admin. Use /connect {message.chat.id} in PM"
        )

    chat_type = _chat_type(message)

    if chat_type == "private":
        return await message.reply_text(
            "Run /connections to view or disconnect from groups!",
            quote=True,
        )

    if chat_type in ("group", "supergroup"):
        group_id = message.chat.id

        try:
            st = await client.get_chat_member(group_id, userid)
            if st.status not in ("administrator", "creator") and userid not in ADMINS:
                return
        except Exception:
            return

        delcon = await delete_connection(str(userid), str(group_id))
        if delcon:
            await message.reply_text(
                "Successfully disconnected from this chat",
                quote=True,
            )
        else:
            await message.reply_text(
                "This chat isn't connected to me!\nDo /connect to connect.",
                quote=True,
            )


@Client.on_message(
    filters.private & filters.command(["connections"]) & filters.user(ADMINS)
)
async def connections(client, message):
    userid = message.from_user.id

    groupids = await all_connections(str(userid))
    if groupids is None:
        return await message.reply_text(
            "There are no active connections!! Connect to some groups first.",
            quote=True,
        )

    buttons = []
    for groupid in groupids:
        try:
            ttl = await client.get_chat(int(groupid))
            title = ttl.title or str(groupid)
            active = await if_active(str(userid), str(groupid))
            act = " - ACTIVE" if active else ""
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{title}{act}",
                        callback_data=f"groupcb:{groupid}:{act}",
                    )
                ]
            )
        except Exception:
            logger.exception("Unable to load connected group %s", groupid)

    if buttons:
        await message.reply_text(
            "Your connected group details ;\n\n",
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True,
        )
    else:
        await message.reply_text(
            "There are no active connections!! Connect to some groups first.",
            quote=True,
        )
