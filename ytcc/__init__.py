# ytcc - The YouTube channel checker
# Copyright (C) 2010  Wolfgang Popp
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

__license__ = "GPLv3"
__version__ = "2.0.0b2"
__author__ = __maintainer__ = "Wolfgang Popp"
__email__ = "mail@wolfgang-popp.de"

from pathlib import Path
import gettext
import sys


def _get_translations_path() -> str:
    path = Path(__file__)
    path = path.parent.joinpath("resources", "locale")
    if path.is_dir():
        return str(path)

    return sys.prefix + "/share/locale"


gettext.bindtextdomain("ytcc", _get_translations_path())
gettext.textdomain("ytcc")
_ = gettext.gettext
