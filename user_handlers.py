"""User-facing command and message handlers for the Telegram bot.

This module implements all user interactions including commands, tariff selection,
payment flow, and receipt upload handling using aiogram 3.x handlers and FSM.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, PhotoSize, Document
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import db
from data_models import TariffType, PaymentStatus, SubscriptionStatus, TariffCallback, PaymentConfirmationCallback, AdminApprovalCallback
from states import PaymentFlow

logger = logging.getLogger(__name__)

# Create router for user handlers
user_router = Router()

# Constants for inline keyboard buttons
BUY_ACCESS_CALLBACK = "buy_access"
MY_SUBSCRIPTION_CALLBACK = "my_subscription"
RECEIPT_UPLOAD_CALLBACK = "receipt_upload"
CANCEL_PAYMENT_CALLBACK = "cancel_payment"


async def send_admin_payment_notification(
    bot: Bot,
    user_id: int,
    username: str,
    tariff: str,
    receipt_file_id: str
) -> bool:
    """Send payment notification to admin with receipt.
    
    Args:
        bot: Bot instance
        user_id: User ID who submitted payment
        username: Username of the user
        tariff: Selected tariff type
        receipt_file_id: Telegram file ID of the receipt
        
    Returns:
        True if notification sent successfully, False otherwise
    """
    try:
        notification_text = (
            f"💳 <b>New Payment Request</b>\n\n"
            f"👤 <b>User:</b> @{username} (ID: {user_id})\n"
            f"🎯 <b>Plan:</b> {tariff.title()}\n"
            f"📅 <b>Date:</b> {date.today()}\n\n"
            f"Please review the payment receipt below and approve or decline."
        )
        
        # Create admin approval keyboard
        kb = InlineKeyboardBuilder()
        approve_data = AdminApprovalCallback(action="approve", user_id=user_id).pack()
        decline_data = AdminApprovalCallback(action="decline", user_id=user_id).pack()
        
        kb.button(text="✅ Approve", callback_data=approve_data)
        kb.button(text="❌ Decline", callback_data=decline_data)
        kb.adjust(1)
        
        # Send notification to admin with receipt
        await bot.send_photo(
            chat_id=config.ADMIN_ID,
            photo=receipt_file_id,
            caption=notification_text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
        
        logger.info(f"Payment notification sent to admin for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send payment notification to admin: {e}")
        return False


def format_subscription_message(subscriber_data: Dict[str, Any]) -> str:
    """Format subscription status message for user.
    
    Args:
        subscriber_data: Dictionary containing subscriber information from database
        
    Returns:
        Formatted message string with subscription details
    """
    if not subscriber_data:
        return "❌ You don't have an active subscription.\n\n💡 Use /start to buy access to our premium channel."
    
    user_id = subscriber_data['user_id']
    username = subscriber_data['username']
    status = subscriber_data['status']
    subscription_type = subscriber_data['subscription_type']
    start_date = subscriber_data['start_date']
    end_date = subscriber_data['end_date']
    
    message_parts = [
        f"📊 <b>Your Subscription Status</b>",
        f"👤 <b>User:</b> @{username} ({user_id})",
        f"📅 <b>Status:</b> {status.title()}",
        f"🎯 <b>Type:</b> {subscription_type.title()}",
    ]
    
    if subscription_type == "lifetime":
        message_parts.append("⏰ <b>Duration:</b> Lifetime (∞)")
    else:
        if start_date:
            message_parts.append(f"🗓️ <b>Start:</b> {start_date}")
        if end_date:
            message_parts.append(f"🏁 <b>End:</b> {end_date}")
            
            # Calculate days remaining
            try:
                end_date_obj = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
                days_remaining = (end_date_obj - date.today()).days
                if days_remaining > 0:
                    message_parts.append(f"⏳ <b>Days remaining:</b> {days_remaining}")
                else:
                    message_parts.append("⚠️ <b>Subscription expired!</b>")
                    status = "expired"
            except (ValueError, TypeError):
                pass
    
    if status == "active":
        message_parts.append("\n✅ <b>Your subscription is active!</b>")
        message_parts.append(f"🔗 <a href='{config.CHANNEL_INVITE_LINK}'>Join Premium Channel</a>")
    elif status == "pending":
        message_parts.append("\n⏳ <b>Your subscription is pending approval.</b>")
        message_parts.append("📋 Please wait for admin verification.")
    elif status == "expired":
        message_parts.append("\n❌ <b>Your subscription has expired.</b>")
        message_parts.append("💡 Use the button below to renew your subscription.")
    
    return "\n".join(message_parts)


def create_main_keyboard() -> InlineKeyboardBuilder:
    """Create main keyboard with primary actions.
    
    Returns:
        InlineKeyboardBuilder instance with main action buttons
    """
    kb = InlineKeyboardBuilder()
    
    # Add action buttons
    kb.button(text="💳 Buy Access / Renew Subscription", callback_data=BUY_ACCESS_CALLBACK)
    kb.button(text="📊 My Subscription", callback_data=MY_SUBSCRIPTION_CALLBACK)
    
    kb.adjust(1)  # Single column layout
    return kb


def create_tariff_selection_keyboard() -> InlineKeyboardBuilder:
    """Create keyboard for tariff selection.
    
    Returns:
        InlineKeyboardBuilder instance with tariff selection buttons
    """
    kb = InlineKeyboardBuilder()
    
    # Add tariff buttons
    monthly_text = f"1 month (${config.TARIFF_MONTHLY})"
    lifetime_text = f"Lifetime (${config.TARIFF_LIFETIME})"
    
    kb.button(text=monthly_text, callback_data=TariffCallback(type="monthly"))
    kb.button(text=lifetime_text, callback_data=TariffCallback(type="lifetime"))
    kb.button(text="❌ Cancel", callback_data=CANCEL_PAYMENT_CALLBACK)
    
    kb.adjust(1)  # Single column layout for better mobile experience
    return kb


def create_payment_keyboard() -> InlineKeyboardBuilder:
    """Create keyboard for payment confirmation.
    
    Returns:
        InlineKeyboardBuilder instance with payment confirmation buttons
    """
    kb = InlineKeyboardBuilder()
    
    # Add payment confirmation buttons
    kb.button(text="💳 I paid and attached receipt", callback_data=PaymentConfirmationCallback(action="confirm"))
    kb.button(text="❌ Cancel Payment", callback_data=PaymentConfirmationCallback(action="cancel"))
    
    kb.adjust(1)  # Single column layout
    return kb


@user_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command - welcome new users and show main options.
    
    Args:
        message: Incoming message object
        state: FSM context for state management
    """
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) started the bot")
    
    # Create subscriber if doesn't exist
    subscriber = db.get_subscriber(user_id)
    if not subscriber:
        success = db.create_subscriber(user_id, username)
        if success:
            logger.info(f"Created new subscriber: {user_id} (@{username})")
        else:
            logger.warning(f"Failed to create subscriber: {user_id}")
    
    # Clear any existing state
    await state.clear()
    
    # Create welcome message
    welcome_text = (
        "👋 <b>Welcome to Premium Channel Bot!</b>\n\n"
        "🎯 This bot allows you to purchase access to our exclusive premium content channel.\n\n"
        "💎 <b>What you get:</b>\n"
        f"• Access to premium content channel: <a href='{config.CHANNEL_INVITE_LINK}'>Join Channel</a>\n"
        "• High-quality exclusive content\n"
        "• Regular updates and new materials\n"
        "• Community access\n\n"
        "📝 <b>Available Commands:</b>\n"
        "• /start - Show welcome menu\n"
        "• /help - Show available commands\n"
        "• /mysubscription - Check your subscription status\n\n"
        "🚀 Get started by clicking the button below!"
    )
    
    # Create and send keyboard
    kb = create_main_keyboard()
    await message.answer(welcome_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    
    logger.info(f"Sent welcome message to user {user_id}")


@user_router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Handle /help command - show available commands and information.
    
    Args:
        message: Incoming message object
    """
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) requested help")
    
    help_text = (
        "📚 <b>Bot Help</b>\n\n"
        "🤖 <b>Available Commands:</b>\n"
        "• /start - Welcome message and main menu\n"
        "• /help - Show this help message\n"
        "• /mysubscription - Check your subscription status\n\n"
        "💳 <b>Subscription Plans:</b>\n"
        f"• Monthly: ${config.TARIFF_MONTHLY} ({config.MONTHLY_DAYS} days)\n"
        f"• Lifetime: ${config.TARIFF_LIFETIME} (unlimited)\n\n"
        "📋 <b>Payment Process:</b>\n"
        "1️⃣ Select your subscription plan\n"
        "2️⃣ Send payment to provided details\n"
        "3️⃣ Upload payment receipt\n"
        "4️⃣ Wait for admin approval\n\n"
        "⏰ <b>Processing Time:</b>\n"
        "Payments are typically processed within 24 hours.\n\n"
        "❓ <b>Need Support?</b>\n"
        "Contact the administrator if you have any issues."
    )
    
    await message.answer(help_text, parse_mode="HTML")
    logger.info(f"Sent help message to user {user_id}")


@user_router.message(Command("mysubscription"))
async def cmd_mysubscription(message: Message) -> None:
    """Handle /mysubscription command - show user's subscription status.
    
    Args:
        message: Incoming message object
    """
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) checked subscription status")
    
    # Get subscriber data
    subscriber_data = db.get_subscriber(user_id)
    
    # Format and send subscription status message
    status_message = format_subscription_message(subscriber_data)
    
    # Create keyboard with appropriate actions
    kb = InlineKeyboardBuilder()
    
    if not subscriber_data or subscriber_data['status'] in ['pending', 'expired']:
        # Show buy/renew button for users without subscription or with expired subscription
        kb.button(text="💳 Buy Access / Renew Subscription", callback_data=BUY_ACCESS_CALLBACK)
    else:
        # Show subscription info button
        kb.button(text="📊 Refresh Status", callback_data=MY_SUBSCRIPTION_CALLBACK)
    
    kb.adjust(1)
    
    await message.answer(status_message, reply_markup=kb.as_markup(), parse_mode="HTML")
    logger.info(f"Sent subscription status to user {user_id}")


@user_router.callback_query(F.data == BUY_ACCESS_CALLBACK)
async def cb_buy_access(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle buy access callback - start tariff selection process.
    
    Args:
        callback_query: Incoming callback query
        state: FSM context for state management
    """
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) initiated subscription purchase")
    
    # Update state to tariff selection
    await state.set_state(PaymentFlow.waiting_tariff_selection)
    
    # Create selection message
    selection_text = (
        "🎯 <b>Choose Your Subscription Plan</b>\n\n"
        "💎 <b>Available Plans:</b>\n\n"
        f"🗓️ <b>Monthly Plan</b>\n"
        f"• Price: ${config.TARIFF_MONTHLY}\n"
        f"• Duration: {config.MONTHLY_DAYS} days\n"
        f"• Access to premium content\n"
        f"• Renew every month\n\n"
        f"♾️ <b>Lifetime Plan</b>\n"
        f"• Price: ${config.TARIFF_LIFETIME}\n"
        f"• Duration: Forever\n"
        f"• Access to all premium content\n"
        f"• One-time payment\n"
        f"• Best value!\n\n"
        "Please select your preferred plan:"
    )
    
    # Create and send tariff selection keyboard
    kb = create_tariff_selection_keyboard()
    await callback_query.message.edit_text(
        selection_text, 
        reply_markup=kb.as_markup(), 
        parse_mode="HTML"
    )
    
    # Answer callback query
    await callback_query.answer()
    logger.info(f"Sent tariff selection to user {user_id}")


@user_router.callback_query(TariffCallback.filter(), PaymentFlow.waiting_tariff_selection)
async def cb_tariff_selected(
    callback_query: CallbackQuery, 
    callback_data: TariffCallback, 
    state: FSMContext
) -> None:
    """Handle tariff selection - show payment details.
    
    Args:
        callback_query: Incoming callback query
        callback_data: Parsed callback data with selected tariff
        state: FSM context for state management
    """
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "Unknown"
    selected_tariff = callback_data.type
    
    logger.info(f"User {user_id} (@{username}) selected {selected_tariff} tariff")
    
    # Determine price based on selected tariff
    if selected_tariff == "monthly":
        price = config.TARIFF_MONTHLY
        tariff_description = f"Monthly Plan ({config.MONTHLY_DAYS} days)"
    else:
        price = config.TARIFF_LIFETIME
        tariff_description = "Lifetime Plan"
    
    # Store payment data in FSM context
    payment_data = {
        "user_id": user_id,
        "username": username,
        "tariff": selected_tariff,
        "price": price,
        "selected_at": datetime.utcnow().isoformat()
    }
    
    await state.update_data(payment_data=payment_data)
    await state.set_state(PaymentFlow.waiting_payment_confirmation)
    
    # Create payment details message
    payment_text = (
        f"💳 <b>Payment Details</b>\n\n"
        f"📋 <b>Selected Plan:</b> {tariff_description}\n"
        f"💰 <b>Amount:</b> ${price}\n\n"
        f"📝 <b>Payment Instructions:</b>\n"
        f"{config.PAYMENT_DETAILS}\n\n"
        "⚠️ <b>Important Notes:</b>\n"
        "• Please send the exact amount shown above\n"
        "• Keep your payment receipt/screenshot\n"
        "• You'll need to upload the receipt after payment\n"
        "• Processing typically takes up to 24 hours\n\n"
        "✅ After completing payment, click the button below and upload your receipt."
    )
    
    # Create and send payment keyboard
    kb = create_payment_keyboard()
    await callback_query.message.edit_text(
        payment_text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    
    # Answer callback query
    await callback_query.answer()
    logger.info(f"Sent payment details to user {user_id} for {selected_tariff} plan")


@user_router.callback_query(PaymentConfirmationCallback.filter(), PaymentFlow.waiting_payment_confirmation)
async def cb_payment_confirmed(
    callback_query: CallbackQuery, 
    callback_data: PaymentConfirmationCallback,
    state: FSMContext
) -> None:
    """Handle payment confirmation - prompt for receipt upload.
    
    Args:
        callback_query: Incoming callback query
        callback_data: Parsed callback data with payment action
        state: FSM context for state management
    """
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "Unknown"
    
    if callback_data.action == "cancel":
        logger.info(f"User {user_id} (@{username}) cancelled payment")
        
        await state.clear()
        
        cancel_text = (
            "❌ <b>Payment Cancelled</b>\n\n"
            "No worries! You can restart the process anytime by clicking the button below."
        )
        
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Buy Access / Renew Subscription", callback_data=BUY_ACCESS_CALLBACK)
        kb.adjust(1)
        
        await callback_query.message.edit_text(
            cancel_text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
        await callback_query.answer("Payment cancelled")
        return
    
    # Payment confirmed - proceed to receipt upload
    logger.info(f"User {user_id} (@{username}) confirmed payment")
    
    # Update state to receipt upload
    await state.set_state(PaymentFlow.waiting_receipt_upload)
    
    receipt_text = (
        "📸 <b>Upload Payment Receipt</b>\n\n"
        "Please upload a clear photo or screenshot of your payment receipt.\n\n"
        "📋 <b>Required:</b>\n"
        "• Screenshot of payment confirmation\n"
        "• Must show the transaction amount\n"
        "• Should include transaction ID or reference\n"
        "• Clear and readable image\n\n"
        "⏳ Your receipt will be reviewed by our admin within 24 hours."
    )
    
    await callback_query.message.edit_text(receipt_text, parse_mode="HTML")
    await callback_query.answer("Please upload your payment receipt")


@user_router.message(PaymentFlow.waiting_receipt_upload, F.photo)
async def handle_receipt_photo(message: Message, state: FSMContext) -> None:
    """Handle receipt photo upload.
    
    Args:
        message: Incoming message with photo
        state: FSM context for state management
    """
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Get the highest quality photo
    photo = message.photo[-1]  # Last item is highest resolution
    file_id = photo.file_id
    
    logger.info(f"User {user_id} (@{username}) uploaded receipt photo: {file_id}")
    
    # Get payment data from state
    data = await state.get_data()
    payment_data = data.get("payment_data", {})
    
    try:
        # Update subscription status to pending and store receipt
        success = db.update_subscriber_status(user_id, "pending")
        if not success:
            logger.error(f"Failed to update subscriber status for user {user_id}")
        
        # Note: In a complete implementation, you might want to store the receipt
        # file_id in a separate payments table. For now, we just update the status.
        
        # Calculate subscription dates
        today = date.today()
        if payment_data.get("tariff") == "monthly":
            end_date = today + timedelta(days=config.MONTHLY_DAYS)
        else:
            end_date = None  # Lifetime subscription
        
        # Update subscription dates and type
        db.update_subscription_dates(
            user_id=user_id,
            start_date=today,
            end_date=end_date,
            subscription_type=payment_data.get("tariff", "monthly")
        )
        
        # Clear state
        await state.clear()
        
        # Send confirmation message
        confirmation_text = (
            "✅ <b>Receipt Received!</b>\n\n"
            "📋 <b>Details:</b>\n"
            f"• User: @{username} ({user_id})\n"
            f"• Plan: {payment_data.get('tariff', 'Unknown')}\n"
            f"• Amount: ${payment_data.get('price', 'Unknown')}\n"
            f"• Receipt: Uploaded successfully\n\n"
            "⏳ <b>Next Steps:</b>\n"
            "• Your payment is being reviewed by our admin\n"
            "• Processing typically takes up to 24 hours\n"
            "• You'll be notified once approved\n"
            "• Check back with /mysubscription for updates\n\n"
            "🙏 Thank you for your patience!"
        )
        
        await message.answer(confirmation_text, parse_mode="HTML")
        
        # Send notification to admin about new payment
        await send_admin_payment_notification(message.bot, user_id, username, payment_data.get("tariff", "Unknown"), file_id)
        
        logger.info(f"Payment receipt submitted by user {user_id} for {payment_data.get('tariff')} plan")
        
    except Exception as e:
        logger.error(f"Error processing receipt for user {user_id}: {e}")
        await message.answer(
            "❌ <b>Error Processing Receipt</b>\n\n"
            "Something went wrong while processing your receipt. Please try again or contact support.",
            parse_mode="HTML"
        )


@user_router.message(PaymentFlow.waiting_receipt_upload, F.document)
async def handle_receipt_document(message: Message, state: FSMContext) -> None:
    """Handle receipt document upload (as alternative to photo).
    
    Args:
        message: Incoming message with document
        state: FSM context for state management
    """
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Check if it's an image file (some users might send images as documents)
    document = message.document
    if document.mime_type and document.mime_type.startswith('image/'):
        # Get payment data from state
        data = await state.get_data()
        payment_data = data.get("payment_data", {})
        
        # Update subscription status to pending
        success = db.update_subscriber_status(user_id, "pending")
        if not success:
            logger.error(f"Failed to update subscriber status for user {user_id}")
        
        # Calculate subscription dates
        today = date.today()
        if payment_data.get("tariff") == "monthly":
            end_date = today + timedelta(days=config.MONTHLY_DAYS)
        else:
            end_date = None  # Lifetime subscription
        
        # Update subscription dates and type
        db.update_subscription_dates(
            user_id=user_id,
            start_date=today,
            end_date=end_date,
            subscription_type=payment_data.get("tariff", "monthly")
        )
        
        # Clear state
        await state.clear()
        
        # Send confirmation message
        confirmation_text = (
            "✅ <b>Receipt Received!</b>\n\n"
            "📋 <b>Details:</b>\n"
            f"• User: @{username} ({user_id})\n"
            f"• Plan: {payment_data.get('tariff', 'Unknown')}\n"
            f"• Amount: ${payment_data.get('price', 'Unknown')}\n"
            f"• Receipt: Uploaded successfully\n\n"
            "⏳ <b>Next Steps:</b>\n"
            "• Your payment is being reviewed by our admin\n"
            "• Processing typically takes up to 24 hours\n"
            "• You'll be notified once approved\n"
            "• Check back with /mysubscription for updates\n\n"
            "🙏 Thank you for your patience!"
        )
        
        await message.answer(confirmation_text, parse_mode="HTML")
        
        # Send notification to admin about new payment
        await send_admin_payment_notification(
            message.bot, 
            user_id, 
            username, 
            payment_data.get("tariff", "Unknown"), 
            document.file_id
        )
        
        logger.info(f"Payment receipt document submitted by user {user_id} for {payment_data.get('tariff')} plan")
        return
    
    logger.info(f"User {user_id} (@{username}) uploaded non-image document: {document.file_name}")
    
    # Reject non-image documents
    await message.answer(
        "❌ <b>Invalid File Type</b>\n\n"
        "Please upload an image file (photo or screenshot) of your payment receipt.\n\n"
        "📸 <b>Accepted formats:</b> JPG, PNG, WEBP\n\n"
        "Try uploading a photo instead of a document.",
        parse_mode="HTML"
    )


@user_router.callback_query(F.data == MY_SUBSCRIPTION_CALLBACK)
async def cb_my_subscription(callback_query: CallbackQuery) -> None:
    """Handle my subscription callback - refresh subscription status.
    
    Args:
        callback_query: Incoming callback query
    """
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) refreshed subscription status")
    
    # Get and format subscriber data
    subscriber_data = db.get_subscriber(user_id)
    status_message = format_subscription_message(subscriber_data)
    
    # Create keyboard
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Refresh Status", callback_data=MY_SUBSCRIPTION_CALLBACK)
    kb.button(text="💳 Buy Access / Renew Subscription", callback_data=BUY_ACCESS_CALLBACK)
    kb.adjust(1)
    
    # Update message
    await callback_query.message.edit_text(
        status_message,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    
    await callback_query.answer("Status refreshed")


@user_router.callback_query(F.data == CANCEL_PAYMENT_CALLBACK)
async def cb_cancel_payment(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Handle payment cancellation.
    
    Args:
        callback_query: Incoming callback query
        state: FSM context for state management
    """
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) cancelled payment process")
    
    # Clear state
    await state.clear()
    
    # Return to main menu
    main_text = (
        "❌ <b>Payment Cancelled</b>\n\n"
        "Your payment process has been cancelled. No charges have been made.\n\n"
        "You can restart the process anytime."
    )
    
    kb = create_main_keyboard()
    await callback_query.message.edit_text(
        main_text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    
    await callback_query.answer("Payment cancelled")


@user_router.message(PaymentFlow.waiting_receipt_upload)
async def handle_invalid_receipt_input(message: Message) -> None:
    """Handle invalid input during receipt upload state.
    
    Args:
        message: Incoming message that is not a photo or document
    """
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) sent invalid input during receipt upload")
    
    await message.answer(
        "❌ <b>Invalid Input</b>\n\n"
        "Please upload a photo or screenshot of your payment receipt.\n\n"
        "📸 <b>How to upload:</b>\n"
        "1. Take a screenshot of your payment confirmation\n"
        "2. Send it as a photo to this chat\n\n"
        "💡 <b>Tip:</b> Make sure the screenshot is clear and shows the transaction amount."
    )


# Error handling for all user handlers
@user_router.message()
async def handle_unknown_message(message: Message) -> None:
    """Handle messages that don't match any specific handler.
    
    Args:
        message: Incoming message object
    """
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) sent unknown message: {message.text}")
    
    await message.answer(
        "🤖 <b>I didn't understand that command.</b>\n\n"
        "📋 <b>Available commands:</b>\n"
        "• /start - Show welcome menu\n"
        "• /help - Show available commands\n"
        "• /mysubscription - Check subscription status\n\n"
        "💡 Use the buttons below for quick actions:",
        reply_markup=create_main_keyboard().as_markup(),
        parse_mode="HTML"
    )


@user_router.callback_query()
async def handle_unknown_callback(callback_query: CallbackQuery) -> None:
    """Handle callback queries that don't match any specific handler.
    
    Args:
        callback_query: Incoming callback query
    """
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) sent unknown callback: {callback_query.data}")
    
    await callback_query.answer("❌ Unknown action")
    
    await callback_query.message.answer(
        "🤔 <b>Something went wrong.</b>\n\n"
        "This action is not available. Please use the menu buttons or type /start.",
        parse_mode="HTML",
        reply_markup=create_main_keyboard().as_markup()
    )