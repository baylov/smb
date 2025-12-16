"""Admin handlers for payment approval and rejection.

This module implements admin-only handlers with middleware to check ADMIN_ID.
Includes handlers for approving/declining payments and sending notifications to users.
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional

from aiogram import Bot, Router, F
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import db
from data_models import AdminApprovalCallback

logger = logging.getLogger(__name__)

# Create router for admin handlers
admin_router = Router()


class AdminFilter(BaseFilter):
    """Filter to check if user is admin."""
    
    async def __call__(self, callback_query: CallbackQuery) -> Dict[str, Any]:
        """Check if the user is the admin."""
        user_id = callback_query.from_user.id
        is_admin = user_id == config.ADMIN_ID
        
        return {"is_admin": is_admin, "user_id": user_id}


def create_approval_keyboard(user_id: int) -> InlineKeyboardBuilder:
    """Create inline keyboard for admin approval actions.
    
    Args:
        user_id: User ID to include in callback data
        
    Returns:
        InlineKeyboardBuilder instance with approval/decline buttons
    """
    kb = InlineKeyboardBuilder()
    
    # Create callback data using the AdminApprovalCallback pattern
    approve_data = AdminApprovalCallback(action="approve", user_id=user_id).pack()
    decline_data = AdminApprovalCallback(action="decline", user_id=user_id).pack()
    
    kb.button(text="✅ Approve", callback_data=approve_data)
    kb.button(text="❌ Decline", callback_data=decline_data)
    kb.adjust(1)
    
    return kb


async def send_user_subscription_confirmation(bot: Bot, user_id: int) -> bool:
    """Send subscription confirmation to user with invitation link.
    
    Args:
        bot: Bot instance
        user_id: User ID to send message to
        
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        confirmation_text = (
            "🎉 <b>Payment Approved!</b>\n\n"
            "✅ Your subscription has been successfully activated.\n\n"
            f"🔗 <a href='{config.CHANNEL_INVITE_LINK}'>Join Premium Channel</a>\n\n"
            "📋 <b>What's included:</b>\n"
            "• Access to exclusive content\n"
            "• Priority support\n"
            "• Regular updates and new features\n\n"
            "🙏 Thank you for your subscription!"
        )
        
        await bot.send_message(
            chat_id=user_id,
            text=confirmation_text,
            parse_mode="HTML"
        )
        
        logger.info(f"Subscription confirmation sent to user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send confirmation to user {user_id}: {e}")
        return False


async def send_user_payment_declined(bot: Bot, user_id: int) -> bool:
    """Send payment declined message to user.
    
    Args:
        bot: Bot instance
        user_id: User ID to send message to
        
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        declined_text = (
            "❌ <b>Payment Not Verified</b>\n\n"
            "Unfortunately, we couldn't verify your payment receipt.\n\n"
            "📋 <b>This could be because:</b>\n"
            "• Unclear or incomplete receipt\n"
            "• Payment amount doesn't match\n"
            "• Transaction not found\n\n"
            "💡 <b>Please try again:</b>\n"
            "1. Upload a clearer receipt screenshot\n"
            "2. Ensure it shows the correct amount\n"
            "3. Include transaction ID or reference\n\n"
            "You can restart the payment process with /start"
        )
        
        await bot.send_message(
            chat_id=user_id,
            text=declined_text,
            parse_mode="HTML"
        )
        
        logger.info(f"Payment declined message sent to user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send declined message to user {user_id}: {e}")
        return False


async def send_admin_confirmation(bot: Bot, action: str, user_data: Dict[str, Any]) -> bool:
    """Send confirmation message to admin about approved/declined payment.
    
    Args:
        bot: Bot instance
        action: Action taken (approve/decline)
        user_data: User data dictionary
        
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        user_id = user_data['user_id']
        username = user_data.get('username', 'Unknown')
        subscription_type = user_data.get('subscription_type', 'Unknown')
        
        if action == "approve":
            message_text = (
                f"✅ <b>Subscription Approved</b>\n\n"
                f"👤 <b>User:</b> @{username} (ID: {user_id})\n"
                f"🎯 <b>Plan:</b> {subscription_type.title()}\n"
                f"📅 <b>Date:</b> {date.today()}\n\n"
                "User has been notified and can now access the premium channel."
            )
        else:  # decline
            message_text = (
                f"❌ <b>Subscription Declined</b>\n\n"
                f"👤 <b>User:</b> @{username} (ID: {user_id})\n"
                f"🎯 <b>Plan:</b> {subscription_type.title()}\n"
                f"📅 <b>Date:</b> {date.today()}\n\n"
                "User has been notified about the declined payment."
            )
        
        await bot.send_message(
            chat_id=config.ADMIN_ID,
            text=message_text,
            parse_mode="HTML"
        )
        
        logger.info(f"Admin confirmation sent for {action} action for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send admin confirmation: {e}")
        return False


@admin_router.callback_query(AdminApprovalCallback.filter())
async def handle_admin_action(
    callback_query: CallbackQuery,
    callback_data: AdminApprovalCallback,
    bot: Bot
) -> None:
    """Handle admin approval/decline actions.
    
    Args:
        callback_query: Incoming callback query
        callback_data: Parsed callback data with action and user_id
        bot: Bot instance
    """
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "Admin"
    
    target_user_id = callback_data.user_id
    action = callback_data.action
    
    logger.info(f"Admin {user_id} (@{username}) performed {action} action for user {target_user_id}")
    
    # Get user data from database
    user_data = db.get_subscriber(target_user_id)
    if not user_data:
        await callback_query.answer("❌ User not found in database", show_alert=True)
        return
    
    try:
        if action == "approve":
            # Update subscription to active status
            success = db.update_subscriber_status(target_user_id, "active")
            if not success:
                logger.error(f"Failed to update status for user {target_user_id}")
                await callback_query.answer("❌ Failed to update user status", show_alert=True)
                return
            
            # Calculate end date based on subscription type
            subscription_type = user_data.get('subscription_type', 'monthly')
            start_date = date.today()
            
            if subscription_type == "lifetime":
                end_date = start_date + timedelta(days=365 * 10)  # 10 years
            else:
                end_date = start_date + timedelta(days=config.MONTHLY_DAYS)
            
            # Update subscription dates
            db.update_subscription_dates(
                user_id=target_user_id,
                start_date=start_date,
                end_date=end_date,
                subscription_type=subscription_type
            )
            
            # Send confirmation to user
            await send_user_subscription_confirmation(bot, target_user_id)
            
            # Send confirmation to admin
            await send_admin_confirmation(bot, "approve", user_data)
            
            # Update callback message
            await callback_query.message.edit_text(
                f"✅ <b>Payment Approved</b>\n\n"
                f"👤 User: @{user_data.get('username', 'Unknown')} ({target_user_id})\n"
                f"🎯 Plan: {subscription_type.title()}\n"
                f"📅 Approved: {date.today()}\n\n"
                "User has been notified and can access the premium channel.",
                parse_mode="HTML"
            )
            
            await callback_query.answer("✅ Payment approved and user notified")
            
        elif action == "decline":
            # Update subscription to expired status
            success = db.update_subscriber_status(target_user_id, "expired")
            if not success:
                logger.error(f"Failed to update status for user {target_user_id}")
                await callback_query.answer("❌ Failed to update user status", show_alert=True)
                return
            
            # Send declined message to user
            await send_user_payment_declined(bot, target_user_id)
            
            # Send confirmation to admin
            await send_admin_confirmation(bot, "decline", user_data)
            
            # Update callback message
            await callback_query.message.edit_text(
                f"❌ <b>Payment Declined</b>\n\n"
                f"👤 User: @{user_data.get('username', 'Unknown')} ({target_user_id})\n"
                f"🎯 Plan: {user_data.get('subscription_type', 'Unknown').title()}\n"
                f"📅 Declined: {date.today()}\n\n"
                "User has been notified about the declined payment.",
                parse_mode="HTML"
            )
            
            await callback_query.answer("❌ Payment declined and user notified")
    
    except Exception as e:
        logger.error(f"Error processing {action} action for user {target_user_id}: {e}")
        await callback_query.answer(f"❌ Error processing {action}", show_alert=True)


@admin_router.callback_query(F.data.startswith("approve_"))
async def handle_legacy_approve_callback(callback_query: CallbackQuery) -> None:
    """Handle legacy approve callback format for backward compatibility.
    
    Args:
        callback_query: Incoming callback query
    """
    # This is for backward compatibility if any old callbacks exist
    try:
        # Extract user_id from callback data like "approve_123456789"
        user_id_str = callback_query.data.replace("approve_", "")
        user_id = int(user_id_str)
        
        # Convert to new callback format and trigger handler
        callback_data = AdminApprovalCallback(action="approve", user_id=user_id)
        await handle_admin_action(callback_query, callback_data, callback_query.bot)
        
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing legacy approve callback: {e}")
        await callback_query.answer("❌ Invalid callback data", show_alert=True)


@admin_router.callback_query(F.data.startswith("decline_"))
async def handle_legacy_decline_callback(callback_query: CallbackQuery) -> None:
    """Handle legacy decline callback format for backward compatibility.
    
    Args:
        callback_query: Incoming callback query
    """
    # This is for backward compatibility if any old callbacks exist
    try:
        # Extract user_id from callback data like "decline_123456789"
        user_id_str = callback_query.data.replace("decline_", "")
        user_id = int(user_id_str)
        
        # Convert to new callback format and trigger handler
        callback_data = AdminApprovalCallback(action="decline", user_id=user_id)
        await handle_admin_action(callback_query, callback_data, callback_query.bot)
        
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing legacy decline callback: {e}")
        await callback_query.answer("❌ Invalid callback data", show_alert=True)


@admin_router.message()
async def handle_non_admin_message(message: Message) -> None:
    """Handle messages from non-admin users.
    
    Args:
        message: Incoming message from non-admin user
    """
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    logger.info(f"Non-admin user {user_id} (@{username}) tried to access admin functionality")
    
    await message.answer(
        "❌ <b>Access Denied</b>\n\n"
        "This functionality is only available to administrators.",
        parse_mode="HTML"
    )


@admin_router.callback_query()
async def handle_non_admin_callback(callback_query: CallbackQuery) -> None:
    """Handle callback queries from non-admin users.
    
    Args:
        callback_query: Incoming callback query from non-admin user
    """
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "Unknown"
    
    logger.info(f"Non-admin user {user_id} (@{username}) tried to access admin callback: {callback_query.data}")
    
    await callback_query.answer("❌ Access denied", show_alert=True)