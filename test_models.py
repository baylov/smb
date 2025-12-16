"""Test file to validate FSM states and data models.

This file demonstrates the usage of the created modules and can be used
for basic validation testing.

Run with: python3 test_models.py (after installing dependencies)
"""

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from states import PaymentFlow
        print("✓ states.py imported successfully")
        print(f"  - PaymentFlow states: {[s for s in dir(PaymentFlow) if not s.startswith('_') and s not in ['model_config', 'model_fields']]}")
    except ImportError as e:
        print(f"✗ Failed to import states.py: {e}")
    
    try:
        from data_models import (
            PaymentData,
            SubscriptionData,
            TariffCallback,
            PaymentConfirmationCallback,
            AdminApprovalCallback,
            TariffType,
            PaymentStatus,
            SubscriptionStatus
        )
        print("✓ data_models.py imported successfully")
        print(f"  - TariffType values: {[t.value for t in TariffType]}")
        print(f"  - PaymentStatus values: {[s.value for s in PaymentStatus]}")
        print(f"  - SubscriptionStatus values: {[s.value for s in SubscriptionStatus]}")
    except ImportError as e:
        print(f"✗ Failed to import data_models.py: {e}")
    
    try:
        from storage import get_fsm_storage, create_memory_storage
        print("✓ storage.py imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import storage.py: {e}")


def test_payment_data():
    """Test PaymentData model."""
    print("\nTesting PaymentData model...")
    
    from data_models import PaymentData, TariffType, PaymentStatus
    
    # Create a payment instance
    payment = PaymentData(
        user_id=123456789,
        username="test_user",
        tariff=TariffType.MONTHLY,
        price=150
    )
    
    print(f"✓ Created PaymentData instance")
    print(f"  - User: {payment.username} (ID: {payment.user_id})")
    print(f"  - Tariff: {payment.tariff}")
    print(f"  - Price: ${payment.price}")
    print(f"  - Status: {payment.status}")
    print(f"  - Created: {payment.created_at}")
    
    # Test serialization
    payment_dict = payment.model_dump()
    print(f"✓ Serialized to dict with {len(payment_dict)} fields")


def test_subscription_data():
    """Test SubscriptionData model."""
    print("\nTesting SubscriptionData model...")
    
    from datetime import date, timedelta
    from data_models import SubscriptionData, TariffType, SubscriptionStatus
    
    # Create a subscription instance
    subscription = SubscriptionData(
        user_id=123456789,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=30),
        status=SubscriptionStatus.ACTIVE,
        subscription_type=TariffType.MONTHLY
    )
    
    print(f"✓ Created SubscriptionData instance")
    print(f"  - User ID: {subscription.user_id}")
    print(f"  - Type: {subscription.subscription_type}")
    print(f"  - Status: {subscription.status}")
    print(f"  - Period: {subscription.start_date} to {subscription.end_date}")


def test_callback_data():
    """Test callback data patterns."""
    print("\nTesting callback data patterns...")
    
    from data_models import (
        TariffCallback,
        PaymentConfirmationCallback,
        AdminApprovalCallback
    )
    
    # Test TariffCallback
    tariff_cb = TariffCallback(type="monthly")
    print(f"✓ TariffCallback created: {tariff_cb.pack()}")
    
    # Test PaymentConfirmationCallback
    payment_cb = PaymentConfirmationCallback(action="confirm")
    print(f"✓ PaymentConfirmationCallback created: {payment_cb.pack()}")
    
    # Test AdminApprovalCallback
    admin_cb = AdminApprovalCallback(action="approve", user_id=123456789)
    print(f"✓ AdminApprovalCallback created: {admin_cb.pack()}")


def test_storage():
    """Test storage configuration."""
    print("\nTesting storage configuration...")
    
    from storage import create_memory_storage, get_fsm_storage
    
    # Test memory storage
    storage = create_memory_storage()
    print(f"✓ Created MemoryStorage: {type(storage).__name__}")
    
    # Test automatic storage selection
    storage = get_fsm_storage()
    print(f"✓ Auto-selected storage: {type(storage).__name__}")


if __name__ == "__main__":
    print("=" * 60)
    print("FSM States and Data Models Validation Test")
    print("=" * 60)
    
    try:
        test_imports()
        test_payment_data()
        test_subscription_data()
        test_callback_data()
        test_storage()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
