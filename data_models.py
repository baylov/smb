"""Data models and callback data patterns for the payment system.

This module defines Pydantic models for payment and subscription data,
as well as callback data patterns for inline keyboard buttons using aiogram 3.x.
"""

from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional

from aiogram.filters.callback_data import CallbackData
from pydantic import BaseModel, Field, field_validator


class TariffType(str, Enum):
    """Enumeration of available subscription tariff types."""
    
    MONTHLY = "monthly"
    LIFETIME = "lifetime"


class PaymentStatus(str, Enum):
    """Enumeration of payment processing statuses."""
    
    PENDING = "pending"
    AWAITING_RECEIPT = "awaiting_receipt"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    DECLINED = "declined"


class SubscriptionStatus(str, Enum):
    """Enumeration of subscription statuses."""
    
    ACTIVE = "active"
    PENDING = "pending"
    EXPIRED = "expired"


class PaymentData(BaseModel):
    """Payment transaction data model.
    
    Attributes:
        user_id: Telegram user ID of the customer.
        username: Telegram username of the customer.
        tariff: Selected subscription tariff type (monthly or lifetime).
        price: Payment amount in USD.
        receipt_file_id: Telegram file ID of the uploaded payment receipt.
        status: Current status of the payment process.
        created_at: Timestamp when the payment record was created.
        updated_at: Timestamp when the payment record was last updated.
    """
    
    user_id: int = Field(..., description="Telegram user ID")
    username: Optional[str] = Field(None, description="Telegram username")
    tariff: TariffType = Field(..., description="Subscription tariff type")
    price: int = Field(..., gt=0, description="Payment amount in USD")
    receipt_file_id: Optional[str] = Field(None, description="Telegram file ID of receipt")
    status: PaymentStatus = Field(
        default=PaymentStatus.PENDING,
        description="Current payment status"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )
    
    @field_validator("updated_at", mode="before")
    @classmethod
    def set_updated_at(cls, v):
        """Automatically update the timestamp."""
        return v or datetime.utcnow()
    
    class Config:
        """Pydantic model configuration."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class SubscriptionData(BaseModel):
    """Subscription data model.
    
    Attributes:
        user_id: Telegram user ID of the subscriber.
        start_date: Subscription start date.
        end_date: Subscription end date (None for lifetime subscriptions).
        status: Current subscription status.
        subscription_type: Type of subscription (monthly or lifetime).
    """
    
    user_id: int = Field(..., description="Telegram user ID")
    start_date: date = Field(..., description="Subscription start date")
    end_date: Optional[date] = Field(None, description="Subscription end date")
    status: SubscriptionStatus = Field(..., description="Subscription status")
    subscription_type: TariffType = Field(..., description="Subscription type")
    
    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v, info):
        """Validate that end_date is after start_date if both are provided."""
        if v is not None and "start_date" in info.data:
            start = info.data["start_date"]
            if v <= start:
                raise ValueError("end_date must be after start_date")
        return v
    
    class Config:
        """Pydantic model configuration."""
        use_enum_values = True
        json_encoders = {
            date: lambda v: v.isoformat(),
        }


class TariffCallback(CallbackData, prefix="tariff"):
    """Callback data for tariff selection buttons.
    
    Used for inline keyboard buttons when users select their subscription plan.
    
    Example callback data strings:
        - tariff:monthly
        - tariff:lifetime
    """
    
    type: Literal["monthly", "lifetime"]


class PaymentConfirmationCallback(CallbackData, prefix="payment"):
    """Callback data for payment confirmation buttons.
    
    Used when users confirm or cancel their payment intent.
    
    Example callback data strings:
        - payment:confirm
        - payment:cancel
    """
    
    action: Literal["confirm", "cancel"]


class AdminApprovalCallback(CallbackData, prefix="admin"):
    """Callback data for admin approval buttons.
    
    Used by administrators to approve or decline user payments.
    
    Example callback data strings:
        - admin:approve:123456789
        - admin:decline:123456789
    """
    
    action: Literal["approve", "decline"]
    user_id: int
