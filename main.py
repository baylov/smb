#!/usr/bin/env python3
"""
Main entry point for Telegram subscription bot.

This module integrates all components:
- Configuration management
- Database initialization  
- Bot and dispatcher setup
- Handler registration
- Scheduler for subscription management
- Graceful shutdown handling
"""

import asyncio
import argparse
import logging
import sys
import signal
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError

import config
import db
import scheduler
from user_handlers import user_router
from admin_handlers import admin_router
from storage import get_fsm_storage


def setup_logging(debug: bool = False) -> None:
    """Configure logging level and format.
    
    Args:
        debug: If True, set level to DEBUG, otherwise INFO
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger(__name__)
    if debug:
        logger.info("Debug logging enabled")


async def verify_configuration() -> bool:
    """Verify critical configuration settings on startup.
    
    Returns:
        True if configuration is valid, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Verify bot token is loaded (already validated in config.py)
        if not config.BOT_TOKEN:
            logger.error("Bot token not configured")
            return False
            
        # Verify admin ID is loaded and valid
        if not config.ADMIN_ID or not isinstance(config.ADMIN_ID, int):
            logger.error("Admin ID not configured or invalid")
            return False
            
        # Verify channel invite link is configured
        if not config.CHANNEL_INVITE_LINK:
            logger.error("Channel invite link not configured")
            return False
            
        # Verify payment details are configured
        if not config.PAYMENT_DETAILS:
            logger.error("Payment details not configured")
            return False
            
        # Verify tariffs are configured and valid
        if not config.TARIFF_MONTHLY or not config.TARIFF_LIFETIME:
            logger.error("Tariff prices not configured")
            return False
            
        logger.info("Configuration verification completed successfully")
        logger.info(f"Admin ID: {config.ADMIN_ID}")
        logger.info(f"Monthly tariff: ${config.TARIFF_MONTHLY}")
        logger.info(f"Lifetime tariff: ${config.TARIFF_LIFETIME}")
        logger.info(f"Monthly duration: {config.MONTHLY_DAYS} days")
        
        return True
        
    except Exception as e:
        logger.exception(f"Configuration verification failed: {e}")
        return False


async def setup_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    """Create and configure bot and dispatcher instances.
    
    Returns:
        Tuple of (Bot, Dispatcher) instances
    """
    logger = logging.getLogger(__name__)
    
    # Create bot instance
    bot = Bot(token=config.BOT_TOKEN)
    logger.info("Bot instance created")
    
    # Get FSM storage (memory or redis based on config)
    storage = get_fsm_storage()
    logger.info(f"FSM storage initialized: {type(storage).__name__}")
    
    # Create dispatcher with storage
    dp = Dispatcher(storage=storage)
    logger.info("Dispatcher created")
    
    return bot, dp


def register_handlers(dp: Dispatcher) -> None:
    """Register all handlers with the dispatcher.
    
    Args:
        dp: Dispatcher instance to register handlers with
    """
    logger = logging.getLogger(__name__)
    
    # Register user handlers
    dp.include_router(user_router)
    logger.info("User handlers registered")
    
    # Register admin handlers
    dp.include_router(admin_router)
    logger.info("Admin handlers registered")


async def start_scheduler_if_enabled(bot: Bot, skip_scheduler: bool) -> Optional[asyncio.Task]:
    """Start the scheduler task if not disabled.
    
    Args:
        bot: Bot instance
        skip_scheduler: If True, don't start the scheduler
        
    Returns:
        Scheduler task if started, None otherwise
    """
    logger = logging.getLogger(__name__)
    
    if skip_scheduler:
        logger.info("Scheduler disabled via CLI argument")
        return None
    
    try:
        task = scheduler.start_scheduler(bot)
        logger.info("Subscription expiration scheduler started")
        return task
    except Exception as e:
        logger.exception(f"Failed to start scheduler: {e}")
        return None


async def startup_hooks(bot: Bot) -> None:
    """Execute startup hooks before starting polling.
    
    Args:
        bot: Bot instance
    """
    logger = logging.getLogger(__name__)
    
    # Log startup message
    logger.info("=" * 50)
    logger.info("🚀 BOT STARTED")
    logger.info("=" * 50)
    
    # Verify configuration
    if not await verify_configuration():
        logger.error("Configuration verification failed. Aborting startup.")
        raise RuntimeError("Configuration verification failed")
    
    # Test bot connection
    try:
        bot_info = await bot.get_me()
        logger.info(f"Bot connected successfully: @{bot_info.username} (ID: {bot_info.id})")
    except TelegramAPIError as e:
        logger.error(f"Failed to connect to Telegram API: {e}")
        raise RuntimeError("Failed to connect to Telegram API") from e


async def shutdown_hooks(bot: Bot, scheduler_task: Optional[asyncio.Task]) -> None:
    """Execute cleanup hooks on shutdown.
    
    Args:
        bot: Bot instance  
        scheduler_task: Scheduler task to cancel if running
    """
    logger = logging.getLogger(__name__)
    
    logger.info("🛑 Bot stopping...")
    
    # Cancel scheduler task if running
    if scheduler_task and not scheduler_task.done():
        logger.info("Stopping scheduler...")
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            logger.info("Scheduler stopped")
        except Exception as e:
            logger.exception(f"Error stopping scheduler: {e}")
    
    # Close bot session
    logger.info("Closing bot session...")
    try:
        await bot.session.close()
        logger.info("Bot session closed")
    except Exception as e:
        logger.exception(f"Error closing bot session: {e}")
    
    logger.info("=" * 50)
    logger.info("⏹️  BOT STOPPED")
    logger.info("=" * 50)


async def main() -> None:
    """Main function that orchestrates the entire bot startup and execution.
    
    This function:
    1. Parses CLI arguments
    2. Sets up logging
    3. Verifies configuration  
    4. Initializes database
    5. Creates bot and dispatcher
    6. Registers handlers
    7. Starts scheduler (if enabled)
    8. Executes startup hooks
    9. Starts polling with graceful shutdown handling
    10. Executes shutdown hooks
    """
    # Parse CLI arguments
    parser = argparse.ArgumentParser(description="Telegram Subscription Bot")
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable DEBUG level logging"
    )
    parser.add_argument(
        "--skip-scheduler", 
        action="store_true", 
        help="Skip starting the subscription expiration scheduler (for testing)"
    )
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(debug=args.debug)
    logger = logging.getLogger(__name__)
    
    try:
        # Database initialization (creates tables if not exist)
        logger.info("Initializing database...")
        db._initialize_db()  # This is called automatically on import, but call explicitly for clarity
        logger.info("Database initialized")
        
        # Setup bot and dispatcher
        bot, dp = await setup_bot_and_dispatcher()
        
        # Register handlers
        register_handlers(dp)
        
        # Start scheduler if enabled
        scheduler_task = await start_scheduler_if_enabled(bot, args.skip_scheduler)
        
        # Execute startup hooks
        await startup_hooks(bot)
        
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            raise KeyboardInterrupt()
            
        # Register signal handlers for graceful shutdown
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
        
        # Start polling for updates
        logger.info("Starting bot polling...")
        await dp.start_polling(bot)
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down gracefully...")
    except Exception as e:
        logger.exception(f"Bot startup or runtime error: {e}")
        raise
    finally:
        # Execute shutdown hooks
        await shutdown_hooks(bot, scheduler_task)


if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())