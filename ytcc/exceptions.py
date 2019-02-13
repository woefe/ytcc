"""Exceptions in their own module to avoid circular imports."""

class YtccException(Exception):
    """A general parent class of all Exceptions that are used in Ytcc."""


class BadURLException(YtccException):
    """Raised when a given URL does not refer to a YouTube channel."""


class DuplicateChannelException(YtccException):
    """Raised when trying to subscribe to a channel the second (or more) time."""


class ChannelDoesNotExistException(YtccException):
    """Raised when the url of a given channel does not exist."""


class InvalidSubscriptionFileError(YtccException):
    """Raised when the given file is not a valid XML file."""


class BadConfigException(YtccException):
    """Raised when error in config file is encountered."""
