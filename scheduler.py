import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import List, Dict, Any

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError

import db

logger = logging.getLogger(__name__)

async def notify_user(bot: Bot, user_id: int, retries: int = 3) -> bool:
    """
    Sends an expiration notification to a user with retry logic.
    """
    message = "Your subscription has expired. Renew to stay in the channel!"
    
    for attempt in range(retries):
        try:
            await bot.send_message(chat_id=user_id, text=message)
            return True
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            logger.warning(f"Rate limited for user {user_id}. Waiting {wait_time}s.")
            await asyncio.sleep(wait_time)
        except TelegramAPIError as e:
            # Check if it's a "user blocked bot" or similar permanent error
            msg = str(e)
            if "blocked" in msg.lower() or "user not found" in msg.lower() or "chat not found" in msg.lower():
                logger.error(f"Cannot send message to user {user_id}: {e}")
                return False
            
            logger.error(f"Failed to send message to user {user_id} (Attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2 * (attempt + 1))
        except Exception as e:
            logger.exception(f"Unexpected error notifying user {user_id}: {e}")
            return False
            
    return False

async def check_expired_subscriptions(bot: Bot):
    """
    Checks for expired subscriptions, notifies users, and updates their status.
    """
    logger.info("Starting expired subscriptions check.")
    start_time = datetime.now()
    
    # 1. Query database for all subscribers with status='active' and end_date < today
    expired_subs = db.list_expired_subscriptions()
    logger.info(f"Found {len(expired_subs)} expired subscriptions.")
    
    processed_count = 0
    
    for sub in expired_subs:
        user_id = sub['user_id']
        username = sub.get('username', 'Unknown')
        logger.info(f"Processing expired subscription for user {user_id} ({username})")
        
        # 2. For each expired subscription: Send user notification
        sent = await notify_user(bot, user_id)
        
        if sent:
            logger.info(f"Notification sent to user {user_id}")
        else:
            logger.warning(f"Could not send notification to user {user_id}")

        # 3. Update status to 'expired' in database
        # We update even if notification failed, because the subscription IS expired.
        if db.update_subscriber_status(user_id, 'expired'):
             logger.info(f"Updated status to 'expired' for user {user_id}")
        else:
             logger.error(f"Failed to update status for user {user_id}")
        
        processed_count += 1

    duration = datetime.now() - start_time
    logger.info(f"Expired subscriptions check completed. Processed {processed_count} users in {duration}.")

async def scheduler_loop(bot: Bot):
    """
    Runs the check_expired_subscriptions task daily at 12:00.
    """
    logger.info("Scheduler started.")
    while True:
        now = datetime.now()
        # Configure scheduler to run once per day (e.g., at 12:00)
        target_time = time(12, 0)
        today_target = datetime.combine(now.date(), target_time)
        
        if now >= today_target:
            # If it's already past 12:00 today, schedule for tomorrow
            next_run = today_target + timedelta(days=1)
        else:
            # Schedule for today at 12:00
            next_run = today_target
            
        sleep_seconds = (next_run - now).total_seconds()
        logger.info(f"Next expiration check scheduled for {next_run} (in {sleep_seconds:.2f} seconds).")
        
        try:
            await asyncio.sleep(sleep_seconds)
            await check_expired_subscriptions(bot)
        except asyncio.CancelledError:
            logger.info("Scheduler task cancelled.")
            break
        except Exception as e:
            logger.exception(f"Error in scheduler loop: {e}")
            # Sleep a bit before retrying loop to avoid busy loop in case of persistent error
            await asyncio.sleep(60)

def start_scheduler(bot: Bot):
    """
    Helper function to start the scheduler as a background task.
    """
    return asyncio.create_task(scheduler_loop(bot))
