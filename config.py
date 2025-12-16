import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("Environment variables loaded from .env file if present.")
except ImportError:
    logger.warning("python-dotenv not installed. Using only system environment variables.")

# Load constants
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
CHANNEL_INVITE_LINK = os.getenv("CHANNEL_INVITE_LINK")
PAYMENT_DETAILS = os.getenv("PAYMENT_DETAILS")
TARIFF_MONTHLY = os.getenv("TARIFF_MONTHLY")
TARIFF_LIFETIME = os.getenv("TARIFF_LIFETIME")
MONTHLY_DAYS = os.getenv("MONTHLY_DAYS", "30")

# Validation
missing_vars = []
if not BOT_TOKEN:
    missing_vars.append("BOT_TOKEN")
if not ADMIN_ID:
    missing_vars.append("ADMIN_ID")
if not CHANNEL_INVITE_LINK:
    missing_vars.append("CHANNEL_INVITE_LINK")
if not PAYMENT_DETAILS:
    missing_vars.append("PAYMENT_DETAILS")
if not TARIFF_MONTHLY:
    missing_vars.append("TARIFF_MONTHLY")
if not TARIFF_LIFETIME:
    missing_vars.append("TARIFF_LIFETIME")

if missing_vars:
    logger.critical(f"Missing required environment variables: {', '.join(missing_vars)}")
    sys.exit(1)

# Type conversion and further validation
try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    logger.critical("ADMIN_ID must be an integer.")
    sys.exit(1)

try:
    TARIFF_MONTHLY = int(TARIFF_MONTHLY) # Assuming integer prices based on example "150"
    TARIFF_LIFETIME = int(TARIFF_LIFETIME) # Assuming integer prices based on example "500"
except ValueError:
    logger.critical("Tariffs (TARIFF_MONTHLY, TARIFF_LIFETIME) must be integers.")
    sys.exit(1)

try:
    MONTHLY_DAYS = int(MONTHLY_DAYS)
except ValueError:
    logger.critical("MONTHLY_DAYS must be an integer.")
    sys.exit(1)

logger.info("Configuration loaded successfully.")
