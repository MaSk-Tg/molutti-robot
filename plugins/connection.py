from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.connections_mdb import add_connection, all_connections, if_active, delete_connection
from info import ADMINS
import logging
import re

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)


def _get_group_id_from_command(message):
    """Return a target group ID from /connect, or None if not supplied."""
    # Pyrogram normally exposes command arguments here:
    # ['/connect', '-1001234567890']
    try:
        command = getattr(message, "command", None) or []
        for arg in command[1:]:
            value = str(arg).strip()
            if re.fullmatch(r"-\d{5,}", value):
                return int(value)
    except Exception:
        pass

    # Fallback for messages where .command is unavailable.
    raw_text = (getattr(message, "text", None)
                or getattr(message, "caption", None)
                or "").strip()

    match = re.search(r"(?<!\d)-\d{5,}(?!\d)", raw_text)
    if match:
        try:
            return int(match.group(0))
        except (TypeError, ValueError):
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
            f"You are anonymous admin. Use /connect {message.chat.id} in PM",
            quote=True,
        )

    # IMPORTANT: initialize chat_type before any branch uses it.
    chat_type = str(message.chat.type).lower()

    # In a group/supergroup, /connect means connect THIS group.
    if chat_type in ("group", "supergroup"):
        group_id = int(message.chat.id)
    else:
        # In PM, /connect must contain the target group ID.
        group_id = _get_group_id_from_command(message)

    if group_id is None:
        await message.reply_text(
            "<b>âŒ Unable to determine the group ID.</b>\n\n"
            "In PM use:\n"
            "<code>/connect -1001234567890</code>\n\n"
            "Or run <code>/connect</code> inside the group.",
            quote=True,
        )
        return

    # Verify that the requesting admin is an admin of the target group.
    try:
        st = await client.get_chat_member(group_id, userid)

        if (
            st.status not in ("administrator", "creator")
            and userid not in ADMINS
        ):
            await message.reply_text(
                "You should be an admin in Given group!",
                quote=True,
            )
            return

    except Exception as e:
        logger.exception("Failed to verify target group/admin: %s", e)
        await message.reply_text(
            "Invalid Group ID!\n\n"
            "If the ID is correct, make sure I'm present in your group.",
            quote=True,
        )
        return

    # Verify that the bot itself is an administrator in the target group.
    try:
        bot_member = await client.get_chat_member(group_id, "me")

        if bot_member.status != "administrator":
            await message.reply_text(
                "Add me as an admin in group",
                quote=True,
            )
            return

        chat = await client.get_chat(group_id)
        title = chat.title or str(group_id)

        addcon = await add_connection(str(group_id), str(userid))

        if addcon:
            await message.reply_text(
                f"Successfully connected to **{title}**\n"
                "Now manage your group from my pm !",
                quote=True,
                parse_mode="md",
            )

            # If /connect was run inside the group, also notify the admin in PM.
            if chat_type in ("group", "supergroup"):
                try:
                    await client.send_message(
                        userid,
                        f"Connected to **{title}** !",
                        parse_mode="md",
                    )
                except Exception as e:
                    logger.exception(
                        "Could not send connection confirmation to PM: %s", e
                    )
        else:
            await message.reply_text(
                "You're already connected to this chat!",
                quote=True,
            )

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
        return await message.reply_text(
            f"You are anonymous admin. Use /connect {message.chat.id} in PM",
            quote=True,
        )

    chat_type = str(message.chat.type).lower()

    if chat_type == "private":
        await message.reply_text(
            "Run /connections to view or disconnect from groups!",
            quote=True,
        )
        return

    if chat_type in ("group", "supergroup"):
        group_id = message.chat.id

        try:
            st = await client.get_chat_member(group_id, userid)
            if (
                st.status not in ("administrator", "creator")
                and userid not in ADMINS
            ):
                return

            delcon = await delete_connection(str(userid), str(group_id))

            if delcon:
                await message.reply_text(
                    "Successfully disconnected from this chat",
                    quote=True,
                )
            else:
                await message.reply_text(
                    "This chat isn't connected to me!\n"
                    "Do /connect to connect.",
                    quote=True,
                )
        except Exception as e:
            logger.exception("Disconnect error: %s", e)
            await message.reply_text(
                "Some error occurred! Try again later.",
                quote=True,
            )


@Client.on_message(
    filters.private
    & filters.command("connections")
    & filters.user(ADMINS)
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
            logger.exception("Failed to load connected group %s", groupid)

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
