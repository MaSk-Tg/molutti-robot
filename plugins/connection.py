from pyrogram import filters, Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from database.connections_mdb import add_connection, all_connections, if_active, delete_connection
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

    chat_type = str(message.chat.type)
    group_id = None

    # In PM, accept the target group ID from both Pyrogram's parsed
    # command arguments and the raw message text.
    if chat_type == "private":
        raw_text = (message.text or message.caption or "").strip()
        candidates = []

        try:
            command = getattr(message, "command", None)
            if command:
                candidates.extend(str(x).strip() for x in command[1:])
        except Exception:
            pass

        # Fallback for cases where message.command does not contain args.
        candidates.extend(re.findall(r"-?\d{5,}", raw_text))

        for candidate in candidates:
            if re.fullmatch(r"-?\d{5,}", candidate):
                try:
                    value = int(candidate)
                    if value != 0:
                        group_id = str(value)
                        break
                except (TypeError, ValueError):
                    continue

        if group_id is None:
            await message.reply_text(
                "<b>❌ Group ID not found.</b>\n\n"
                "Use:\n"
                "<code>/connect -1001234567890</code>\n\n"
                "Or run <code>/connect</code> inside the group.",
                quote=True,
            )
            return

    elif chat_type in ("group", "supergroup"):
        group_id = str(message.chat.id)

    if group_id is None:
        await message.reply_text(
            "<b>❌ Unable to determine the group ID.</b>\n\n"
            "Use <code>/connect -1001234567890</code> in PM "
            "or run <code>/connect</code> inside the group.",
            quote=True,
        )
        return

    try:
        st = await client.get_chat_member(int(group_id), userid)
        if (
            st.status != "administrator"
            and st.status != "creator"
            and userid not in ADMINS
        ):
            await message.reply_text(
                "You should be an admin in Given group!",
                quote=True,
            )
            return
    except Exception as e:
        logger.exception(e)
        await message.reply_text(
            "Invalid Group ID!\n\n"
            "If correct, Make sure I'm present in your group!!",
            quote=True,
        )
        return

    try:
        st = await client.get_chat_member(int(group_id), "me")
        if st.status == "administrator":
            ttl = await client.get_chat(int(group_id))
            title = ttl.title

            addcon = await add_connection(str(group_id), str(userid))
            if addcon:
                await message.reply_text(
                    f"Successfully connected to **{title}**\n"
                    "Now manage your group from my pm !",
                    quote=True,
                    parse_mode="md",
                )

                if chat_type in ("group", "supergroup"):
                    await client.send_message(
                        userid,
                        f"Connected to **{title}** !",
                        parse_mode="md",
                    )
            else:
                await message.reply_text(
                    "You're already connected to this chat!",
                    quote=True,
                )
        else:
            await message.reply_text(
                "Add me as an admin in group",
                quote=True,
            )
    except Exception as e:
        logger.exception(e)
        await message.reply_text(
            "Some error occurred! Try again later.",
            quote=True,
        )
        return


@Client.on_message((filters.private | filters.group) & filters.command('disconnect') & filters.user(ADMINS))
async def deleteconnection(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == "private":
        await message.reply_text("Run /connections to view or disconnect from groups!", quote=True)

    elif chat_type in ["group", "supergroup"]:
        group_id = message.chat.id

        st = await client.get_chat_member(group_id, userid)
        if (
                st.status != "administrator"
                and st.status != "creator"
                and str(userid) not in ADMINS
        ):
            return

        delcon = await delete_connection(str(userid), str(group_id))
        if delcon:
            await message.reply_text("Successfully disconnected from this chat", quote=True)
        else:
            await message.reply_text("This chat isn't connected to me!\nDo /connect to connect.", quote=True)


@Client.on_message(filters.private & filters.command(["connections"]) & filters.user(ADMINS))
async def connections(client, message):
    userid = message.from_user.id

    groupids = await all_connections(str(userid))
    if groupids is None:
        await message.reply_text(
            "There are no active connections!! Connect to some groups first.",
            quote=True
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
                        text=f"{title}{act}", callback_data=f"groupcb:{groupid}:{act}"
                    )
                ]
            )
        except:
            pass
    if buttons:
        await message.reply_text(
            "Your connected group details ;\n\n",
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )
    else:
        await message.reply_text(
            "There are no active connections!! Connect to some groups first.",
            quote=True
        )
