import uuid
from datetime import datetime, timezone, timedelta
import time
import functools
import asyncio
import logging
import random
import re
import os # For os.path.splitext in sanitize_filename
from typing import Callable, Any, TypeVar, Coroutine, Dict, TYPE_CHECKING

# Assuming constants.py is in purse.utils
from src.utils.constants import WORDS_PER_MINUTE

if TYPE_CHECKING:
    from src.config_manager import ConfigManager # For type hinting ConfigManager

logger = logging.getLogger(__name__)

# Type variable for the return type of the decorated function
R = TypeVar('R')

def generate_uuid() -> str:
    """Generates a new UUID string."""
    return str(uuid.uuid4())

def get_current_timestamp_iso() -> str:
    """Returns the current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()

def parse_iso_timestamp(timestamp_str: str) -> datetime:
    """
    Parses an ISO 8601 timestamp string into a naive datetime object if it ends with 'Z',
    or an aware object if timezone info is included.
    To ensure consistency, it's often better to convert to UTC after parsing if it's naive.
    For simplicity as per workplan, direct fromisoformat is used.
    If timestamp_str is from get_current_timestamp_iso(), it will be timezone-aware (UTC).
    """
    return datetime.fromisoformat(timestamp_str)


def exponential_backoff_retry(
    max_attempts: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True
) -> Callable[..., Callable[..., R | Coroutine[Any, Any, R]]]:
    """
    Decorator for retrying a function with exponential backoff.
    Works for both synchronous and asynchronous functions.
    Uses decorator arguments for retry parameters.
    """
    def decorator(func: Callable[..., R | Coroutine[Any, Any, R]]) -> Callable[..., R | Coroutine[Any, Any, R]]:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> R:
                nonlocal initial_delay # Allow modification if needed, though not modified here
                current_delay = initial_delay
                for attempt in range(1, max_attempts + 1):
                    try:
                        # Ensure the function being awaited is indeed the passed async func
                        # The type hint `func: Callable[..., Coroutine[Any, Any, R]]` would be more specific here
                        # but the union type is for the decorator's input.
                        # We've already established it's a coroutine function.
                        return await func(*args, **kwargs) # type: ignore
                    except Exception as e:
                        logger.warning(f"🟡 Attempt {attempt}/{max_attempts} failed for async {func.__name__}: {e}")
                        if attempt == max_attempts:
                            logger.error(f"🛑 All {max_attempts} attempts failed for async {func.__name__}.")
                            raise
                        
                        delay_with_jitter = current_delay
                        if jitter:
                            delay_with_jitter += random.uniform(0, current_delay * 0.25) # up to 25% jitter
                        
                        logger.info(f"Retrying async {func.__name__} in {delay_with_jitter:.2f} seconds...")
                        await asyncio.sleep(delay_with_jitter)
                        current_delay = min(current_delay * 2, max_delay)
                # This part should ideally not be reached if max_attempts > 0, due to raise in loop
                raise RuntimeError(f"Retry logic completed without success or error for async {func.__name__}")
            return async_wrapper # type: ignore 
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> R:
                nonlocal initial_delay
                current_delay = initial_delay
                for attempt in range(1, max_attempts + 1):
                    try:
                        # Type assertion for sync function's return type
                        result: R = func(*args, **kwargs) # type: ignore
                        return result
                    except Exception as e:
                        logger.warning(f"🟡 Attempt {attempt}/{max_attempts} failed for sync {func.__name__}: {e}")
                        if attempt == max_attempts:
                            logger.error(f"🛑 All {max_attempts} attempts failed for sync {func.__name__}.")
                            raise
                        
                        delay_with_jitter = current_delay
                        if jitter:
                            delay_with_jitter += random.uniform(0, current_delay * 0.25) # up to 25% jitter

                        logger.info(f"Retrying sync {func.__name__} in {delay_with_jitter:.2f} seconds...")
                        time.sleep(delay_with_jitter)
                        current_delay = min(current_delay * 2, max_delay)
                # This part should not be reached
                raise RuntimeError(f"Retry logic completed without success or error for sync {func.__name__}")
            return sync_wrapper # type: ignore
    return decorator # type: ignore

def get_retry_config(config_manager: 'ConfigManager') -> Dict[str, Any]:
    """
    Fetches retry parameters from ConfigManager.
    """
    return {
        "max_attempts": config_manager.get('retry.max_attempts', 5),
        "initial_delay": config_manager.get('retry.initial_delay_seconds', 1.0), # Ensure float
        "max_delay": config_manager.get('retry.max_delay_seconds', 60.0),   # Ensure float
        "jitter": config_manager.get('retry.jitter', True) # Added from common practice, not in workplan spec for this func
    }

def calculate_estimated_read_time(word_count: int) -> int:
    """
    Calculates estimated reading time in minutes.
    Ensures at least 1 minute for very short texts if word_count > 0.
    """
    if word_count <= 0:
        return 0
    # Using WORDS_PER_MINUTE from constants.py
    minutes = round(word_count / WORDS_PER_MINUTE)
    return max(1, minutes) if minutes == 0 and word_count > 0 else minutes


def sanitize_filename(filename: str, max_len: int = 200) -> str:
    """
    Sanitizes a string to be a valid filename.
    - Removes invalid characters.
    - Removes leading/trailing whitespace and periods.
    - Optionally limits length (total length including extension).
    """
    if not filename:
        return "untitled"

    # Remove characters that are explicitly invalid on Windows and/or POSIX common filesystems.
    # \x00-\x1f are control characters.
    # Others are: < > : " / \ | ? *
    # Some filesystems also don't like leading/trailing spaces or periods for filenames/directories.
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
    
    # Remove leading/trailing whitespace and periods from the whole filename
    filename = filename.strip(' .')

    # If the filename becomes empty after sanitization (e.g., "...")
    if not filename:
        return "untitled"

    # Limit length (optional, but good practice for cross-platform compatibility)
    # This should apply to the filename part, not including a long path.
    if max_len > 0 and len(filename) > max_len:
        name_part, ext_part = os.path.splitext(filename)
        # Max length for the name part, considering the extension length
        # Max_len is for the whole filename "name.ext"
        if len(ext_part) > max_len / 2: # Avoid overly long extensions consuming all space
            ext_part = ext_part[:int(max_len/2)]

        available_len_for_name = max_len - len(ext_part)
        if available_len_for_name <= 0: # Should not happen if max_len is reasonable
             # This means extension is too long, truncate filename to something very short
            name_part = name_part[:1] if name_part else "f" # Fallback to a single char if name_part is empty
        else:
            name_part = name_part[:available_len_for_name]
        
        filename = name_part + ext_part
        
        # After truncation, strip again in case it ended with a period.
        filename = filename.strip(' .')
        if not filename: # If somehow it became empty after length limiting
            return "untitled_truncated"


    # Final check if filename is empty or just a period (which can be problematic)
    if not filename or filename == ".":
        return "untitled"
        
    return filename

# Example Usage (not part of the module's public API, for testing or illustration)
if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
    logger.addHandler(console_handler)
    logging.getLogger().addHandler(console_handler) # Also add to root for other loggers like asyncio

    print(f"Generated UUID: {generate_uuid()}")
    print(f"Current ISO Timestamp: {get_current_timestamp_iso()}")
    ts = get_current_timestamp_iso()
    print(f"Parsed ISO Timestamp: {parse_iso_timestamp(ts)}")

    print(f"Read time for 300 words: {calculate_estimated_read_time(300)} min(s)")
    print(f"Read time for 50 words: {calculate_estimated_read_time(50)} min(s)")
    print(f"Read time for 0 words: {calculate_estimated_read_time(0)} min(s)")


    # Test sanitize_filename
    filenames_to_test = [
        "My Document.pdf", "  leading/trailing spaces.txt  ", "file:with?invalid*chars.doc",
        "another.long.filename.that.might.exceed.the.limit.and.needs.truncation.very.very.long.indeed.ext",
        "", ".", "..", "...", ".hiddenfile", " leadingdot.txt",
        "a" * 250 + ".txt", "short." + "a" * 250,
        "no_ext_long_" + "a"*250,
        "<>&*?/.evil.txt"
    ]
    for fn in filenames_to_test:
        sanitized = sanitize_filename(fn, max_len=60) # Test with shorter max_len
        print(f"Original: '{fn}' -> Sanitized (max 60): '{sanitized}'")

    # Test retry decorator (sync)
    @exponential_backoff_retry(max_attempts=3, initial_delay=0.1, max_delay=1.0)
    def might_fail_sync(fail_times: int):
        might_fail_sync.attempts = getattr(might_fail_sync, 'attempts', 0) + 1
        print(f"Calling might_fail_sync (attempt {might_fail_sync.attempts})...")
        if might_fail_sync.attempts <= fail_times:
            raise ValueError(f"Simulated sync failure on attempt {might_fail_sync.attempts}")
        print("might_fail_sync succeeded.")
        return "Sync success"

    try:
        print("\nTesting sync retry (should fail 2 times, succeed on 3rd):")
        might_fail_sync(fail_times=2)
        might_fail_sync.attempts = 0 # Reset for next test
        print("\nTesting sync retry (should fail all 3 times):")
        might_fail_sync(fail_times=3)
    except Exception as e:
        print(f"Caught expected exception after retries: {e}")

    # Test retry decorator (async)
    @exponential_backoff_retry(max_attempts=3, initial_delay=0.1, max_delay=1.0)
    async def might_fail_async(fail_times: int):
        might_fail_async.attempts = getattr(might_fail_async, 'attempts', 0) + 1
        print(f"Calling might_fail_async (attempt {might_fail_async.attempts})...")
        if might_fail_async.attempts <= fail_times:
            raise ValueError(f"Simulated async failure on attempt {might_fail_async.attempts}")
        await asyncio.sleep(0.01) # Simulate async work
        print("might_fail_async succeeded.")
        return "Async success"

    async def run_async_tests():
        try:
            print("\nTesting async retry (should fail 2 times, succeed on 3rd):")
            await might_fail_async(fail_times=2)
            might_fail_async.attempts = 0 # Reset for next test
            print("\nTesting async retry (should fail all 3 times):")
            await might_fail_async(fail_times=3)
        except Exception as e:
            print(f"Caught expected exception after async retries: {e}")

    print("\nRunning async tests...")
    asyncio.run(run_async_tests())
