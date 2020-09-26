# ytcc - The YouTube channel checker
# Copyright (C) 2020  Wolfgang Popp
#
# This file is part of ytcc.
#
# ytcc is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ytcc is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ytcc.  If not, see <http://www.gnu.org/licenses/>.

"""Exceptions in their own module to avoid circular imports."""


class YtccException(Exception):
    """A general parent class of all Exceptions that are used in Ytcc."""


class BadURLException(YtccException):
    """Raised when a given URL does not refer to a YouTube channel."""


class NameConflictError(YtccException):
    """Raised when trying to subscribe to a channel the second (or more) time."""


class PlaylistDoesNotExistException(YtccException):
    """Raised when the url of a given channel does not exist."""


class InvalidSubscriptionFileError(YtccException):
    """Raised when the given file is not a valid XML file."""


class BadConfigException(YtccException):
    """Raised when error in config file is encountered."""


class IncompatibleDatabaseVersion(YtccException):
    """Raised when the database has an incompatible version."""
