"""Eval file for f-string logging detection.

Lines with expected errors are annotated with::
    # UAR001: <col>
"""
import logging

logger = logging.getLogger(__name__)


# Bad: f-string in logger call
logger.info(f"user={user}")  # UAR001: 0


# Good: parameterized logging
logger.info("user=%s", user)
logger.debug("debug %s", x)
logger.warning("warn %s", y)
logger.error("error %s", z)
logger.critical("critical %s", w)


# Good: string concatenation (not ideal but not f-string)
logger.info("user=" + str(user))


# Good: percent formatting
logger.info("user=%s" % user)


# Good: str.format() - also not ideal but not f-string
logger.info("user={}".format(user))
