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

from ytcc.database import Database, MappedVideo, Video, MappedPlaylist, Playlist
from ytcc.exceptions import (
    YtccException,
    BadURLException,
    NameConflictError,
    PlaylistDoesNotExistException,
    InvalidSubscriptionFileError,
    BadConfigException,
    IncompatibleDatabaseVersion,
)

__license__ = "GPLv3"
__version__ = "2.6.1"
__author__ = __maintainer__ = "Wolfgang Popp"
__email__ = "mail@wolfgang-popp.de"

__all__ = [
    "Database",
    "MappedVideo",
    "Video",
    "MappedPlaylist",
    "Playlist",
    "YtccException",
    "BadURLException",
    "NameConflictError",
    "PlaylistDoesNotExistException",
    "InvalidSubscriptionFileError",
    "BadConfigException",
    "IncompatibleDatabaseVersion",
]
