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

"""The YouTube channel checker.

Command Line tool to keep track of your favourite YouTube channels without
signing up for a Google account.
"""

from ytcc.database import Database, MappedPlaylist, MappedVideo, Playlist, Video
from ytcc.exceptions import (
    BadConfigError,
    BadURLError,
    IncompatibleDatabaseVersionError,
    InvalidSubscriptionFileError,
    NameConflictError,
    PlaylistDoesNotExistError,
    YtccError,
)

__version__ = "2.7.1"

__all__ = [
    "BadConfigError",
    "BadURLError",
    "Database",
    "IncompatibleDatabaseVersionError",
    "InvalidSubscriptionFileError",
    "MappedPlaylist",
    "MappedVideo",
    "NameConflictError",
    "Playlist",
    "PlaylistDoesNotExistError",
    "Video",
    "YtccError",
]
