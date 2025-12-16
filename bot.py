"""Main bot file demonstrating how to integrate user handlers.

This file shows how to set up the bot with all handlers including the user handlers.
In a real deployment, this would be your main entry point.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from user_handlers import user_router

logger = logging.getLogger(__name__)


async def main():
    """Main function to start the bot."""
    # Initialize bot and dispatcher
    bot = Bot(token=config.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Include routers
    dp.include_router(user_router)
    
    # Start polling
    try:
        logger.info("Starting bot...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())