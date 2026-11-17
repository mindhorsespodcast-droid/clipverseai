"""Errors the worker understands.

UserFacingError  -> show `message` to the creator as-is; don't retry (e.g. "this isn't a video").
RetryLater       -> a service asked us to wait (free-tier limit); try again after `seconds`.
Anything else    -> unexpected; retried a few times, then a generic plain-English message.
"""


class UserFacingError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class RetryLater(Exception):
    def __init__(self, seconds: float, reason: str):
        super().__init__(reason)
        self.seconds = max(5.0, float(seconds))
        self.reason = reason


class ConfigError(Exception):
    """A key or setting is missing. The message says exactly what to add to .env."""
