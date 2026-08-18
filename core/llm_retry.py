"""
Chimeras v2.3 — LLM Retry with Exponential Backoff

Wraps LLM calls with retry logic. LLM calls retry (transient failures,
rate limits). Tool execution NEVER retries — double-executing a pentest
tool on a live target is a liability.

Usage:
    from core.llm_retry import llm_retry

    @llm_retry(max_attempts=3, base_delay=2.0)
    def my_llm_call(prompt, system, **kwargs):
        return router.generate(prompt, system, **kwargs)
"""

import time
import functools
import logging

logger = logging.getLogger("chimeras.retry")


class LLMRetryError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


def llm_retry(max_attempts: int = 3, base_delay: float = 2.0, max_delay: float = 30.0):
    """
    Decorator for LLM calls with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including first).
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries (caps exponential growth).

    Catches: ConnectionError, TimeoutError, RuntimeError, Exception
        (with "rate" or "429" or "timeout" in the message).

    Does NOT catch: ValueError, TypeError, json.JSONDecodeError
        (these are logic errors, not transient failures).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
                    # Logic errors — don't retry, propagate immediately
                    raise
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    # Check if this is a retryable error
                    retryable = any(
                        keyword in error_msg
                        for keyword in ("rate", "429", "timeout", "timed out",
                                        "connection", "503", "502", "500",
                                        "temporarily", "overloaded", "reset")
                    )
                    if not retryable and attempt == 1:
                        # Non-retryable on first attempt — raise immediately
                        raise
                    if attempt < max_attempts:
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                        logger.warning(
                            f"LLM call attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"LLM call failed after {max_attempts} attempts: {e}"
                        )

            # All attempts exhausted
            raise LLMRetryError(
                f"LLM call failed after {max_attempts} attempts. Last error: {last_error}"
            ) from last_error

        return wrapper
    return decorator


import json  # needed for JSONDecodeError check above