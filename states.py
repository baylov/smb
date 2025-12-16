"""FSM states for user payment flow.

This module defines finite state machine states used in the bot's payment workflow
using aiogram 3.x StatesGroup and State classes.
"""

from aiogram.fsm.state import State, StatesGroup


class PaymentFlow(StatesGroup):
    """States for the payment flow process.
    
    This state group manages the complete payment workflow from initial contact
    through tariff selection, payment confirmation, receipt upload, and admin approval.
    """
    
    start = State()
    waiting_tariff_selection = State()
    waiting_payment_confirmation = State()
    waiting_receipt_upload = State()
    waiting_admin_approval = State()
