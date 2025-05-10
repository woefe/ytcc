# ytcc - The YouTube channel checker
# Copyright (C) 2025  Wolfgang Popp
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


class YtccError(Exception):
    """A general parent class of all Exceptions that are used in Ytcc."""


class BadURLError(YtccError):
    """Raised when a given URL cannot be handled by youtube-dl."""


class NameConflictError(YtccError):
    """Raised when trying to subscribe to a playlist the second (or more) time."""


class PlaylistDoesNotExistError(YtccError):
    """Raised when the url of a given playlist does not exist."""


class InvalidSubscriptionFileError(YtccError):
    """Raised when the given file is not a valid XML file."""


class BadConfigError(YtccError):
    """Raised when error in config file is encountered."""


class IncompatibleDatabaseVersionError(YtccError):
    """Raised when the database has an incompatible version."""
