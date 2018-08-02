import datetime
import os
import argparse
import ytcc
import ytcc.cli
from dateutil import parser as date_parser
from gettext import gettext as _


def is_directory(string: str) -> str:
    if not os.path.isdir(string):
        msg = _("%r is not a directory") % string
        raise argparse.ArgumentTypeError(msg)

    return string


def is_date(string: str) -> datetime.datetime:
    try:
        return date_parser.parse(string)
    except ValueError:
        msg = _("%r is not a valid date") % string
        raise argparse.ArgumentTypeError(msg)


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=_("ytcc is a commandline YouTube client that keeps track of your favorite "
                      "channels. The --list, --watch, --download, --mark-watched options can be "
                      "combined with filter options --channel-filter, --include-watched, --since,"
                      " --to"))

    parser.add_argument("-a", "--add-channel",
                        help=_("add a new channel. NAME is the name displayed by ytcc. URL is the "
                               "url of the channel's front page"),
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

    parser.add_argument("-q", "--search",
                        help=_("searches for the given PATTERN. The pattern can specify one of the"
                               " three columns 'channel', 'title', 'description'. If no column is "
                               "specified, all columns are searched. The pattern can also specify "
                               "'*' wildcards. Example: --search 'title:box*' will find all video "
                               "that have a word that starts with 'box' in their title. If this "
                               "flag is enabled, the -f, -n, " "-s, -t flags will be ignored."),
                        metavar="PATTERN")

    parser.add_argument("-p", "--path",
                        help=_("set the download path to PATH"),
                        metavar="PATH",
                        type=is_directory)

    parser.add_argument("-g", "--no-description",
                        help=_("do not print the video description before playing the video"),
                        action="store_true")

    parser.add_argument("-o", "--columns",
                        help=_("specifies which columns will be printed when listing videos. COL "
                               "can be any of %(columns)s. All columns can be enabled with "
                               "'all'") % {
                                 "columns": str(ytcc.cli.table_header)
                             },
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
