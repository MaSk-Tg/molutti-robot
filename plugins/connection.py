from pyrogram import filters, Client
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


@Client.on_message(
    (filters.private | filters.group)
    & filters.command("connect")
    & filters.user(ADMINS)
)
async def addconnection(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(
            f"You are anonymous admin. Use /connect {message.chat.id} in PM"
        )

    chat_type = str(message.chat.type).lower()
    group_id = None

    # /connect <group_id> in PM
    if chat_type == "private":
        raw_text = (message.text or message.caption or "").strip()

        # Pyrogram normally puts arguments in message.command.
        candidates = []
        command = getattr(message, "command", None)
        if command:
            candidates.extend(str(item).strip() for item in command[1:])

        # Fallback for raw text, including /connect@BotUsername -100...
        candidates.extend(re.findall(r"-100\d{5,}", raw_text))
        candidates.extend(re.findall(r"(?<!\d)-\d{5,}", raw_text))

        for candidate in candidates:
            if re.fullmatch(r"-\d{5,}", candidate):
                try:
                    value = int(candidate)
                except (TypeError, ValueError):
                    continue
                if value < 0:
                    group_id = value
                    break

        if group_id is None:
            await message.reply_text(
                "<b>❌ Enter the Group ID correctly.</b>\n\n"
                "Use:\n"
                "<code>/connect -1001234567890</code>\n\n"
                "The bot must already be present in that group.\n"
                "Or run <code>/connect</code> directly inside the group.",
                quote=True,
            )
            return

    # /connect directly inside a group/supergroup
    elif "group" in chat_type:
        group_id = message.chat.id

    else:
        await message.reply_text(
            "<b>❌ Unable to determine the group ID.</b>\n\n"
            "Use <code>/connect -1001234567890</code> in PM "
            "or run <code>/connect</code> inside the group.",
            quote=True,
        )
        return

    try:
        # Verify that the requesting user is an admin of the target group.
        st = await client.get_chat_member(int(group_id), userid)
        if st.status not in ("administrator", "creator") and userid not in ADMINS:
            await message.reply_text(
                "You should be an admin in the given group!",
                quote=True,
            )
            return
    except Exception as e:
        logger.exception("Unable to verify group/user: %s", e)
        await message.reply_text(
            "❌ Invalid Group ID!\n\n"
            "If the ID is correct, make sure the bot and you are present in the group.",
            quote=True,
        )
        return

    try:
        # The bot itself must be an administrator in the target group.
        bot_member = await client.get_chat_member(int(group_id), "me")
        if bot_member.status not in ("administrator", "creator"):
            await message.reply_text(
                "❌ Please add me as an admin in the group first.",
                quote=True,
            )
            return

        chat = await client.get_chat(int(group_id))
        title = chat.title or "this group"

        addcon = await add_connection(str(group_id), str(userid))
        if not addcon:
            await message.reply_text(
                "You're already connected to this chat!",
                quote=True,
            )
            return

        await message.reply_text(
            f"Successfully connected to **{title}**\n"
            "Now manage your group from my PM!",
            quote=True,
            parse_mode="md",
        )

        # When /connect was run inside the group, also notify the admin in PM.
        if "group" in chat_type:
            try:
                await client.send_message(
                    userid,
                    f"Connected to **{title}**!",
                    parse_mode="md",
                )
            except Exception as e:
                logger.exception("Unable to send PM confirmation: %s", e)

    except Exception as e:
        logger.exception("Connection error: %s", e)
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
        return await message.reply(
            f"You are anonymous admin. Use /connect {message.chat.id} in PM"
        )

    chat_type = str(message.chat.type).lower()

    if chat_type == "private":
        await message.reply_text(
            "Run /connections to view or disconnect from groups!",
            quote=True,
        )
        return

    if "group" in chat_type:
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
        await message.reply_text(
            "There are no active connections!! Connect to some groups first.",
            quote=True,
        )
        return

    buttons = []
    for groupid in groupids:
        try:
            ttl = await client.get_chat(int(groupid))
            title = ttl.title
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
            pass

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
