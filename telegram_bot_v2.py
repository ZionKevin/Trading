# -*- coding: utf-8 -*-
"""Telegram bot with DM + channel support."""
import logging
import re
import asyncio
from telegram import Bot, Update
from telegram.error import TelegramError
from price_check import check_prices
from trend_check import check_trends
from market_status import market_overview
from scalp_check import check_h1_trend, check_m5_scalp, check_m15_scalp

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8818803199:AAECR9hCDj5Cnw91YR75vqg6pUkhLMG08QY"
bot = Bot(token=BOT_TOKEN)

last_update_id = 0


async def get_updates():
    """Poll for new messages."""
    global last_update_id
    try:
        updates = await bot.get_updates(offset=last_update_id + 1, timeout=30)
        if updates:
            last_update_id = max(u.update_id for u in updates)
        return updates
    except Exception as e:
        logger.error(f"getUpdates error: {e}")
        return []


async def send_reply(chat_id, text):
    """Send message to chat."""
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        logger.info(f"[SENT] {len(text)} chars to {chat_id}")
        return True
    except Exception as e:
        logger.error(f"send_reply error: {e}")
        return False


async def handle_command(chat_id, text):
    """Route command to handler."""
    cmd = text.lower().strip()

    try:
        if "/price" in cmd:
            logger.info(f"/price from {chat_id}")
            reply = check_prices()
            await send_reply(chat_id, reply)
        elif "/trend" in cmd:
            logger.info(f"/trend from {chat_id}")
            reply = check_trends()
            await send_reply(chat_id, reply)
        elif "/status" in cmd:
            logger.info(f"/status from {chat_id}")
            reply = market_overview()
            await send_reply(chat_id, reply)
        elif "/h1" in cmd:
            logger.info(f"/h1 from {chat_id}")
            reply = check_h1_trend()
            await send_reply(chat_id, reply)
        elif "/m5" in cmd:
            logger.info(f"/m5 from {chat_id}")
            reply = check_m5_scalp()
            await send_reply(chat_id, reply)
        elif "/m15" in cmd:
            logger.info(f"/m15 from {chat_id}")
            reply = check_m15_scalp()
            await send_reply(chat_id, reply)
    except Exception as e:
        logger.error(f"handle_command error: {e}")
        await send_reply(chat_id, f"❌ Error: {str(e)[:100]}")


async def run_bot():
    """Main bot loop."""
    logger.info("Bot started. Listening for commands...")

    while True:
        try:
            updates = await get_updates()

            for update in updates:
                # Handle direct messages
                if update.message and update.message.text:
                    text = update.message.text
                    chat_id = update.message.chat.id
                    if text.startswith("/"):
                        logger.info(f"[MSG] {text} from {chat_id}")
                        await handle_command(chat_id, text)

                # Handle channel posts
                elif update.channel_post and update.channel_post.text:
                    text = update.channel_post.text
                    chat_id = update.channel_post.chat.id
                    if text.startswith("/"):
                        logger.info(f"[CH] {text} from {chat_id}")
                        await handle_command(chat_id, text)

            if not updates:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Bot stopped.")
            break
        except Exception as e:
            logger.error(f"Bot loop error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_bot())
