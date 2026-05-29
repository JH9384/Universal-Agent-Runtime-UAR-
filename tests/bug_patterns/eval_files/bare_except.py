"""Eval file for bare except Exception detection.

Lines with expected errors are annotated with::
    # UAR002: <col>
"""
import logging

logger = logging.getLogger(__name__)


# Bad: bare except Exception without logging
try:
    pass
except Exception:  # UAR002: 0
    pass


# Good: specific exception
try:
    pass
except ValueError:
    pass


# Good: except Exception with logging
try:
    pass
except Exception as exc:
    logger.warning("Error: %s", exc)


# Good: except Exception with logging using error level
try:
    pass
except Exception:
    logger.error("Something went wrong")


# Good: re-raise
try:
    pass
except Exception:
    raise


# Good: re-raise after logging
try:
    pass
except Exception as exc:
    logger.warning("Error: %s", exc)
    raise
