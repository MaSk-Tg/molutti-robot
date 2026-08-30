from pyrogram import Client, filters
import datetime
import time
from database.users_chats_db import db
from info import ADMINS
from utils import broadcast_messages
import asyncio


async def _send_to_chat(bot, chat_id, b_msg):
    try:
        await b_msg.copy(chat_id)
        return True, "Success"
    except Exception as e:
        error = str(e).lower()
        if "peer id invalid" in error or "user is blocked" in error:
            return False, "Blocked"
        if "chat not found" in error:
            return False, "Deleted"
        return False, "Error"


# USER BROADCAST
# Reply to any message and use: /broadcast
@Client.on_message(filters.command("broadcast") & filters.user(ADMINS) & filters.reply)
async def user_broadcast(bot, message):
    users = await db.get_all_users()
    b_msg = message.reply_to_message

    sts = await message.reply_text(
        "📢 User Broadcast Started..."
    )

    start_time = time.time()
    total_users = await db.total_users_count()
    done = success = blocked = deleted = failed = 0

    async for user in users:
        pti, sh = await broadcast_messages(int(user["id"]), b_msg)

        if pti:
            success += 1
        elif sh == "Blocked":
            blocked += 1
        elif sh == "Deleted":
            deleted += 1
        elif sh == "Error":
            failed += 1

        done += 1
        await asyncio.sleep(2)

        if not done % 20:
            await sts.edit(
                f"📢 User Broadcast in progress...\n\n"
                f"Total Users: {total_users}\n"
                f"Completed: {done} / {total_users}\n"
                f"Success: {success}\n"
                f"Blocked: {blocked}\n"
                f"Deleted: {deleted}\n"
                f"Failed: {failed}"
            )

    time_taken = datetime.timedelta(seconds=int(time.time() - start_time))

    await sts.edit(
        f"✅ User Broadcast Completed!\n\n"
        f"Completed in: {time_taken}\n"
        f"Total Users: {total_users}\n"
        f"Completed: {done} / {total_users}\n"
        f"Success: {success}\n"
        f"Blocked: {blocked}\n"
        f"Deleted: {deleted}\n"
        f"Failed: {failed}"
    )


# GROUP BROADCAST
# Reply to any message and use: /gbroadcast
@Client.on_message(filters.command("gbroadcast") & filters.user(ADMINS) & filters.reply)
async def group_broadcast(bot, message):
    groups = await db.get_all_chats()
    b_msg = message.reply_to_message

    sts = await message.reply_text(
        "📢 Group Broadcast Started..."
    )

    start_time = time.time()
    total_groups = await db.total_chat_count()
    done = success = disabled = deleted = failed = 0

    async for group in groups:
        group_id = int(group["id"])

        # Skip disabled groups
        chat_status = group.get("chat_status", {})
        if chat_status.get("is_disabled", False):
            disabled += 1
            done += 1
            continue

        ok, status = await _send_to_chat(bot, group_id, b_msg)

        if ok:
            success += 1
        elif status == "Deleted":
            deleted += 1
        else:
            failed += 1

        done += 1
        await asyncio.sleep(1)

        if not done % 10:
            await sts.edit(
                f"📢 Group Broadcast in progress...\n\n"
                f"Total Groups: {total_groups}\n"
                f"Completed: {done} / {total_groups}\n"
                f"Success: {success}\n"
                f"Disabled: {disabled}\n"
                f"Deleted/Unavailable: {deleted}\n"
                f"Failed: {failed}"
            )

    time_taken = datetime.timedelta(seconds=int(time.time() - start_time))

    await sts.edit(
        f"✅ Group Broadcast Completed!\n\n"
        f"Completed in: {time_taken}\n"
        f"Total Groups: {total_groups}\n"
        f"Completed: {done} / {total_groups}\n"
        f"Success: {success}\n"
        f"Disabled: {disabled}\n"
        f"Deleted/Unavailable: {deleted}\n"
        f"Failed: {failed}"
    )
