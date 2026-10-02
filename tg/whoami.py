"""Check the Telegram setup without posting: bot identity, whether TELEGRAM_CHAT_ID is a chat the bot can post in,
and the channels/groups the bot has seen recently (with their ids). The token is never printed."""
import os

from .telegram import Bot, TelegramError


def main():
    bot = Bot()
    me = bot.call("getMe")
    print(f"Bot: @{me.get('username')} ({me.get('first_name')}) — token works")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if chat:
        try:
            c = bot.call("getChat", {"chat_id": chat}, tries=1)
            print(f"TELEGRAM_CHAT_ID points to: {c.get('type')} '{c.get('title') or c.get('username')}' (id {c.get('id')})")
            if c.get("type") != "channel":
                print("::warning::TELEGRAM_CHAT_ID is not a channel")
            try:
                m = bot.call("getChatMember", {"chat_id": c["id"], "user_id": me["id"]}, tries=1)
                can = m.get("status") == "administrator" and m.get("can_post_messages", False)
                print(f"Bot status in it: {m.get('status')}; can post: {can}")
            except TelegramError:
                can = False  # Telegram hides the member list from bots that are not admins
                print("Bot is not an admin of this channel")
            if not can:
                print("::warning::make the bot an admin of the channel with 'Post messages' allowed")
            else:
                print("All set: the bot can post in the channel.")
        except TelegramError as e:
            print(f"::warning::TELEGRAM_CHAT_ID ({chat!r}) is not usable: {e}. "
                  "Use the channel's @username (with @) or its -100… id, not the bot's name.")
    seen = {}
    for u in bot.call("getUpdates", {"allowed_updates": '["channel_post","my_chat_member","message"]'}, tries=1):
        for k in ("channel_post", "my_chat_member", "message"):
            ch = (u.get(k) or {}).get("chat")
            if ch and ch.get("type") in ("channel", "supergroup", "group"):
                seen[ch["id"]] = f"{ch.get('type')} '{ch.get('title')}'" + (f" @{ch['username']}" if ch.get("username") else "")
    if seen:
        print("Chats the bot has seen recently (use the id or @username as TELEGRAM_CHAT_ID):")
        for i, t in seen.items():
            print(f"  {i}  {t}")
    else:
        print("The bot hasn't seen any channel yet: add it as admin, post anything in the channel, then run this again.")


if __name__ == "__main__":
    main()
