import functools
import logging
import time
import uuid
from contextlib import contextmanager

from django.core.cache import cache

logger = logging.getLogger(__name__)


class DistributedLock:
    """
    A distributed lock implementation using Django's cache backend.

    This lock can be used to prevent race conditions in distributed environments
    where multiple processes or servers might try to access the same resource
    simultaneously.
    """

    def __init__(self, key, expires=60, timeout=10, poll_interval=0.1):
        """
        Initialize a distributed lock.

        Args:
            key (str): The unique identifier for the lock
            expires (int): The number of seconds after which the lock expires
            timeout (int): The maximum number of seconds to wait to acquire the lock
            poll_interval (float): The interval in seconds to check if lock can be acquired
        """
        self.key = f"lock:{key}"
        self.expires = expires
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._lock_id = str(uuid.uuid4())

    def acquire(self):
        """
        Attempt to acquire the lock.

        Returns:
            bool: True if the lock was acquired, False otherwise
        """
        logger.debug(f"Attempting to acquire lock for {self.key}")
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            # Try to add the key to the cache only if it doesn't exist
            if cache.add(self.key, self._lock_id, self.expires):
                logger.debug(f"Lock acquired for {self.key}")
                return True

            # If we can't acquire the lock, wait before trying again
            time.sleep(self.poll_interval)

        logger.warning(
            f"Failed to acquire lock for {self.key} after {self.timeout} seconds"
        )
        return False

    def release(self):
        """
        Release the lock if it's owned by this instance.

        Returns:
            bool: True if the lock was released, False otherwise
        """
        logger.debug(f"Attempting to release lock for {self.key}")

        # Only release the lock if it's owned by this instance
        if cache.get(self.key) == self._lock_id:
            cache.delete(self.key)
            logger.debug(f"Lock released for {self.key}")
            return True

        logger.warning(
            f"Failed to release lock for {self.key} - lock not owned by this instance"
        )
        return False


@contextmanager
def distributed_lock(key, expires=60, timeout=10, poll_interval=0.1):
    """
    Context manager for acquiring and releasing a distributed lock.

    Args:
        key (str): The unique identifier for the lock
        expires (int): The number of seconds after which the lock expires
        timeout (int): The maximum number of seconds to wait to acquire the lock
        poll_interval (float): The interval in seconds to check if lock can be acquired

    Yields:
        bool: True if the lock was acquired, False otherwise
    """
    lock = DistributedLock(key, expires, timeout, poll_interval)
    acquired = lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()


def with_distributed_lock(key_func=None, expires=60, timeout=10, poll_interval=0.1):
    """
    Decorator for wrapping a function with a distributed lock.

    Args:
        key_func (callable, optional): A function that returns the lock key. If None,
            the lock key will be the function name.
        expires (int): The number of seconds after which the lock expires
        timeout (int): The maximum number of seconds to wait to acquire the lock
        poll_interval (float): The interval in seconds to check if lock can be acquired

    Returns:
        callable: The decorated function
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = func.__name__

            with distributed_lock(key, expires, timeout, poll_interval) as acquired:
                if not acquired:
                    logger.warning(
                        f"Failed to acquire lock for {key}, execution skipped"
                    )
                    return None
                return func(*args, **kwargs)

        return wrapper

    return decorator
