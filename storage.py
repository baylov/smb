"""FSM storage configuration for the bot.

This module provides factory functions to create FSM storage instances
for managing conversation state data. Supports both in-memory storage
(for MVP and development) and Redis storage (for production).
"""

import logging
import os
from typing import Optional

from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

logger = logging.getLogger(__name__)


def get_fsm_storage(redis_url: Optional[str] = None) -> BaseStorage:
    """Create and return an FSM storage instance.
    
    This function returns the appropriate storage backend based on configuration.
    By default, it uses in-memory storage for MVP deployments. If a Redis URL
    is provided, it will use Redis storage for production deployments.
    
    Args:
        redis_url: Optional Redis connection URL. If provided, Redis storage
                   will be used. Format: redis://host:port/db or
                   redis://user:password@host:port/db
    
    Returns:
        An instance of BaseStorage (either MemoryStorage or RedisStorage).
    
    Examples:
        >>> # Use in-memory storage (default for MVP)
        >>> storage = get_fsm_storage()
        
        >>> # Use Redis storage for production
        >>> storage = get_fsm_storage("redis://localhost:6379/0")
    """
    
    redis_url = redis_url or os.getenv("REDIS_URL")
    
    if redis_url:
        try:
            # Check if redis package is available
            import redis.asyncio
            
            # Check if aiogram Redis storage is available  
            from aiogram.fsm.storage.redis import RedisStorage
            
            # Create Redis connection and storage
            redis_client = redis.asyncio.Redis.from_url(redis_url, decode_responses=True)
            storage = RedisStorage(redis=redis_client)
            logger.info("Using Redis FSM storage: %s", redis_url)
            return storage
        except ImportError:
            logger.warning(
                "Redis not available. Install with: pip install redis. "
                "Falling back to MemoryStorage."
            )
        except Exception as e:
            logger.error(
                "Failed to initialize Redis storage: %s. Falling back to MemoryStorage.",
                e,
                exc_info=True
            )
    
    logger.info("Using in-memory FSM storage (suitable for MVP)")
    return MemoryStorage()


def create_memory_storage() -> MemoryStorage:
    """Create an in-memory storage instance.
    
    This storage type keeps all FSM data in RAM and is suitable for:
    - Development and testing
    - MVP deployments with single-instance bots
    - Scenarios where state persistence is not critical
    
    Note: All state data will be lost when the bot restarts.
    
    Returns:
        A MemoryStorage instance.
    """
    
    logger.info("Creating MemoryStorage for FSM")
    return MemoryStorage()


def create_redis_storage(redis_url: str) -> BaseStorage:
    """Create a Redis storage instance.
    
    This storage type persists FSM data in Redis and is suitable for:
    - Production deployments
    - Multi-instance bot deployments
    - Scenarios requiring state persistence across restarts
    
    Args:
        redis_url: Redis connection URL. Format: redis://host:port/db
    
    Returns:
        A RedisStorage instance.
    
    Raises:
        ImportError: If the redis package is not installed.
        Exception: If Redis connection cannot be established.
    """
    
    from aiogram.fsm.storage.redis import RedisStorage
    from redis.asyncio import Redis
    
    redis = Redis.from_url(redis_url, decode_responses=True)
    storage = RedisStorage(redis=redis)
    logger.info("Created RedisStorage for FSM: %s", redis_url)
    return storage
