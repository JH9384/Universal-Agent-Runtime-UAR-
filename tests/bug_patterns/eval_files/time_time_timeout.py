"""Eval file for time.time() used for timeout detection.

Lines with expected errors are annotated with::
    # UAR003: <col>
"""
import time


# Bad: time.time() + timeout
deadline = time.time() + 30  # UAR003: 11


# Good: time.time() - t0 for elapsed measurement
elapsed = time.time() - t0


# Good: simple timestamp recording
created_at = time.time()


# Good: time.monotonic() for timeout
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    pass
