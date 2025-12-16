# FSM States and Data Models Usage Guide

This document explains how to use the FSM (Finite State Machine) states and data models for the payment flow in the Telegram bot.

## Overview

The payment flow system consists of three main modules:

1. **states.py** - Defines FSM states for the payment workflow
2. **data_models.py** - Defines Pydantic models and callback data patterns
3. **storage.py** - Configures FSM storage backends

## FSM States (states.py)

The `PaymentFlow` state group manages the complete payment workflow:

```python
from states import PaymentFlow

# State transitions:
# 1. start -> Initial state when user begins interaction
# 2. waiting_tariff_selection -> User needs to select monthly/lifetime plan
# 3. waiting_payment_confirmation -> User needs to confirm payment intent
# 4. waiting_receipt_upload -> User needs to upload payment receipt
# 5. waiting_admin_approval -> Admin needs to approve/decline payment
```

### Example Usage

```python
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from states import PaymentFlow

router = Router()

@router.message(PaymentFlow.start)
async def handle_start(message: Message, state: FSMContext):
    # User is in the start state
    await message.answer("Select your tariff...")
    await state.set_state(PaymentFlow.waiting_tariff_selection)
```

## Data Models (data_models.py)

### PaymentData

Stores information about a payment transaction:

```python
from data_models import PaymentData, TariffType, PaymentStatus

# Create a payment record
payment = PaymentData(
    user_id=123456789,
    username="john_doe",
    tariff=TariffType.MONTHLY,
    price=150,
    status=PaymentStatus.PENDING
)

# Update receipt after user uploads it
payment.receipt_file_id = "AgACAgIAAxkBAAI..."
payment.status = PaymentStatus.AWAITING_APPROVAL

# Access data
print(f"User {payment.username} selected {payment.tariff} for ${payment.price}")
```

### SubscriptionData

Stores subscription information:

```python
from datetime import date, timedelta
from data_models import SubscriptionData, TariffType, SubscriptionStatus

# Create a subscription
subscription = SubscriptionData(
    user_id=123456789,
    start_date=date.today(),
    end_date=date.today() + timedelta(days=30),  # None for lifetime
    status=SubscriptionStatus.ACTIVE,
    subscription_type=TariffType.MONTHLY
)
```

### Callback Data Patterns

The module provides three callback data classes for inline keyboards:

#### 1. TariffCallback

Used for tariff selection buttons:

```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from data_models import TariffCallback

keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(
            text="Monthly - $150",
            callback_data=TariffCallback(type="monthly").pack()
        )
    ],
    [
        InlineKeyboardButton(
            text="Lifetime - $500",
            callback_data=TariffCallback(type="lifetime").pack()
        )
    ]
])

# In the callback handler:
from aiogram import F

@router.callback_query(TariffCallback.filter())
async def handle_tariff_selection(
    callback: CallbackQuery,
    callback_data: TariffCallback,
    state: FSMContext
):
    tariff_type = callback_data.type  # "monthly" or "lifetime"
    # Process tariff selection...
```

#### 2. PaymentConfirmationCallback

Used for payment confirmation buttons:

```python
from data_models import PaymentConfirmationCallback

keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(
            text="✅ Confirm Payment",
            callback_data=PaymentConfirmationCallback(action="confirm").pack()
        )
    ],
    [
        InlineKeyboardButton(
            text="❌ Cancel",
            callback_data=PaymentConfirmationCallback(action="cancel").pack()
        )
    ]
])

@router.callback_query(PaymentConfirmationCallback.filter())
async def handle_payment_confirmation(
    callback: CallbackQuery,
    callback_data: PaymentConfirmationCallback
):
    if callback_data.action == "confirm":
        # User confirmed payment
        pass
    else:
        # User cancelled
        pass
```

#### 3. AdminApprovalCallback

Used by administrators to approve/decline payments:

```python
from data_models import AdminApprovalCallback

# In admin notification handler
def create_admin_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Approve",
                callback_data=AdminApprovalCallback(
                    action="approve",
                    user_id=user_id
                ).pack()
            ),
            InlineKeyboardButton(
                text="❌ Decline",
                callback_data=AdminApprovalCallback(
                    action="decline",
                    user_id=user_id
                ).pack()
            )
        ]
    ])

@router.callback_query(AdminApprovalCallback.filter())
async def handle_admin_approval(
    callback: CallbackQuery,
    callback_data: AdminApprovalCallback
):
    user_id = callback_data.user_id
    action = callback_data.action  # "approve" or "decline"
    # Process admin decision...
```

## FSM Storage (storage.py)

The storage module provides flexible storage configuration:

### In-Memory Storage (Default for MVP)

```python
from storage import get_fsm_storage

# Automatic selection (uses environment variable or defaults to memory)
storage = get_fsm_storage()

# Or explicitly create memory storage
from storage import create_memory_storage
storage = create_memory_storage()
```

### Redis Storage (For Production)

```python
from storage import get_fsm_storage

# Provide Redis URL
storage = get_fsm_storage("redis://localhost:6379/0")

# Or set REDIS_URL environment variable and use default
# export REDIS_URL=redis://localhost:6379/0
storage = get_fsm_storage()

# Or explicitly create Redis storage
from storage import create_redis_storage
storage = create_redis_storage("redis://localhost:6379/0")
```

### Bot Initialization

```python
from aiogram import Bot, Dispatcher
from storage import get_fsm_storage
import config

bot = Bot(token=config.BOT_TOKEN)
storage = get_fsm_storage()  # Auto-selects based on environment
dp = Dispatcher(storage=storage)
```

## Complete Example Flow

Here's a simplified example of the complete payment flow:

```python
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from states import PaymentFlow
from data_models import (
    PaymentData,
    TariffCallback,
    PaymentConfirmationCallback,
    AdminApprovalCallback,
    TariffType,
    PaymentStatus
)
from storage import get_fsm_storage
import config

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"Monthly - ${config.TARIFF_MONTHLY}",
            callback_data=TariffCallback(type="monthly").pack()
        )],
        [InlineKeyboardButton(
            text=f"Lifetime - ${config.TARIFF_LIFETIME}",
            callback_data=TariffCallback(type="lifetime").pack()
        )]
    ])
    
    await message.answer("Choose your subscription plan:", reply_markup=keyboard)
    await state.set_state(PaymentFlow.waiting_tariff_selection)

@router.callback_query(TariffCallback.filter(), PaymentFlow.waiting_tariff_selection)
async def handle_tariff(
    callback: CallbackQuery,
    callback_data: TariffCallback,
    state: FSMContext
):
    tariff = TariffType(callback_data.type)
    price = config.TARIFF_MONTHLY if tariff == TariffType.MONTHLY else config.TARIFF_LIFETIME
    
    # Store payment data
    payment = PaymentData(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        tariff=tariff,
        price=price
    )
    await state.update_data(payment=payment.model_dump())
    
    # Show payment details
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ I've sent the payment",
            callback_data=PaymentConfirmationCallback(action="confirm").pack()
        )],
        [InlineKeyboardButton(
            text="❌ Cancel",
            callback_data=PaymentConfirmationCallback(action="cancel").pack()
        )]
    ])
    
    await callback.message.answer(
        f"Payment details:\n{config.PAYMENT_DETAILS}\n\nAmount: ${price}",
        reply_markup=keyboard
    )
    await state.set_state(PaymentFlow.waiting_payment_confirmation)
    await callback.answer()

@router.callback_query(
    PaymentConfirmationCallback.filter(F.action == "confirm"),
    PaymentFlow.waiting_payment_confirmation
)
async def handle_confirmation(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Please upload your payment receipt (photo):")
    await state.set_state(PaymentFlow.waiting_receipt_upload)
    await callback.answer()

@router.message(PaymentFlow.waiting_receipt_upload, F.photo)
async def handle_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    payment_data = data.get("payment", {})
    
    # Update payment with receipt
    payment_data["receipt_file_id"] = message.photo[-1].file_id
    payment_data["status"] = PaymentStatus.AWAITING_APPROVAL.value
    await state.update_data(payment=payment_data)
    
    # Notify admin
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Approve",
                callback_data=AdminApprovalCallback(
                    action="approve",
                    user_id=message.from_user.id
                ).pack()
            ),
            InlineKeyboardButton(
                text="❌ Decline",
                callback_data=AdminApprovalCallback(
                    action="decline",
                    user_id=message.from_user.id
                ).pack()
            )
        ]
    ])
    
    bot = message.bot
    await bot.send_photo(
        config.ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"Payment from @{message.from_user.username}\n"
                f"Tariff: {payment_data['tariff']}\n"
                f"Amount: ${payment_data['price']}",
        reply_markup=keyboard
    )
    
    await message.answer("Receipt received! Waiting for admin approval...")
    await state.set_state(PaymentFlow.waiting_admin_approval)

# Initialize bot
bot = Bot(token=config.BOT_TOKEN)
storage = get_fsm_storage()
dp = Dispatcher(storage=storage)
dp.include_router(router)
```

## Enums Reference

### TariffType
- `MONTHLY`: Monthly subscription
- `LIFETIME`: Lifetime subscription

### PaymentStatus
- `PENDING`: Initial state
- `AWAITING_RECEIPT`: Waiting for user to upload receipt
- `AWAITING_APPROVAL`: Waiting for admin approval
- `APPROVED`: Payment approved by admin
- `DECLINED`: Payment declined by admin

### SubscriptionStatus
- `ACTIVE`: Active subscription
- `PENDING`: Pending activation
- `EXPIRED`: Expired subscription

## Environment Variables

For Redis storage support, add to your .env file:

```env
REDIS_URL=redis://localhost:6379/0
```

If not provided, the system will use in-memory storage by default.
