# ytcc - The YouTube channel checker
# Copyright (C) 2018  Wolfgang Popp
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

import datetime
import os
import argparse
import ytcc
import ytcc.cli
from dateutil import parser as date_parser
from gettext import gettext as _


def is_directory(string: str) -> str:
    if not os.path.isdir(string):
        msg = _("{!r} is not a directory").format(string)
        raise argparse.ArgumentTypeError(msg)

    return string


def is_date(string: str) -> datetime.datetime:
    try:
        return date_parser.parse(string)
    except ValueError:
        msg = _("{!r} is not a valid date").format(string)
        raise argparse.ArgumentTypeError(msg)


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=_("ytcc is a commandline YouTube client that keeps track of your favorite "
                      "channels. The --list, --watch, --download, --mark-watched options can be "
                      "combined with filter options --channel-filter, --include-watched, --since,"
                      " --to"))

    parser.add_argument("-a", "--add-channel",
                        help=_("add a new channel. NAME is the name displayed by ytcc. URL is the "
                               "url of the channel's front page or the URL of any video published "
                               "by the channel"),
                        nargs=2,
                        metavar=("NAME", "URL"))

    parser.add_argument("-c", "--list-channels",
                        help=_("print a list of all subscribed channels"),
                        action="store_true")

    parser.add_argument("-r", "--delete-channel",
                        help=_("unsubscribe from the channel identified by 'ID'"),
                        metavar="ID",
                        nargs='+',
                        type=str)

    parser.add_argument("-u", "--update",
                        help=_("update the video list"),
                        action="store_true")

    parser.add_argument("-l", "--list",
                        help=_("print a list of videos that match the criteria given by the "
                               "filter options"),
                        action="store_true")

    parser.add_argument("-w", "--watch",
                        help=_("play the videos identified by 'ID'. Omitting the ID will play all "
                               "videos specified by the filter options"),
                        nargs='*',
                        type=int,
                        metavar="ID")

    parser.add_argument("-d", "--download",
                        help=_("download the videos identified by 'ID'. The videos are saved "
                               "in $HOME/Downloads by default. Omitting the ID will download "
                               "all videos that match the criteria given by the filter options"),
                        nargs="*",
                        type=int,
                        metavar="ID")

    parser.add_argument("-m", "--mark-watched",
                        help=_("mark videos identified by ID as watched. Omitting the ID will mark"
                               " all videos that match the criteria given by the filter options as "
                               "watched"),
                        nargs='*',
                        type=int,
                        metavar="ID")

    parser.add_argument("-f", "--channel-filter",
                        help=_("plays, lists, marks, downloads only videos from channels defined "
                               "in the filter"),
                        nargs='+',
                        type=str,
                        metavar="NAME")

    parser.add_argument("-n", "--include-watched",
                        help=_("include already watched videos to filter rules"),
                        action="store_true")

    parser.add_argument("-s", "--since",
                        help=_("includes only videos published after the given date"),
                        metavar="YYYY-MM-DD",
                        type=is_date)

    parser.add_argument("-t", "--to",
                        help=_("includes only videos published before the given date"),
                        metavar="YYYY-MM-DD",
                        type=is_date)

    parser.add_argument("-p", "--path",
                        help=_("set the download path to PATH"),
                        metavar="PATH",
                        type=is_directory)

    parser.add_argument("-g", "--no-description",
                        help=_("do not print the video description before playing the video"),
                        action="store_true")

    parser.add_argument("-o", "--columns",
                        help=_("specifies which columns will be printed when listing videos. COL "
                               "can be any of {columns}. All columns can be enabled with "
                               "'all'").format(columns=ytcc.cli.table_header),
                        nargs='+',
                        metavar="COL",
                        choices=["all", *ytcc.cli.table_header])

    parser.add_argument("--no-header",
                        help=_("do not print the header of the table when listing videos"),
                        action="store_true")

    parser.add_argument("-x", "--no-video",
                        help=_("plays or downloads only the audio part of a video"),
                        action="store_true")

    parser.add_argument("-y", "--disable-interactive",
                        help=_("disables the interactive mode"),
                        action="store_true")

    parser.add_argument("--import-from",
                        help=_("import YouTube channels from YouTube's subscription export "
                               "(available at https://www.youtube.com/subscription_manager)"),
                        metavar="PATH",
                        type=argparse.FileType("r"))

    parser.add_argument("--cleanup",
                        help=_("removes old videos from the database and shrinks the size of the "
                               "database file"),
                        action="store_true")

    parser.add_argument("-v", "--version",
                        help=_("output version information and exit"),
                        action="store_true")

    parser.add_argument("--bug-report-info",
                        help=_("print info to include in a bug report"),
                        action="store_true")

    return parser.parse_args()
