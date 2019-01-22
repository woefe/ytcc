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

import itertools
import readline
import sys
from collections import OrderedDict

import shutil
import signal
import textwrap as wrap
from datetime import datetime
from gettext import gettext as _
from typing import List, Iterable, Optional, TextIO, NamedTuple, Callable, Any, Set

from ytcc import core, arguments
from ytcc.video import Video

ytcc_core = core.Ytcc()
interactive_enabled = True
description_enabled = True
no_video = False
download_path = ""

header_enabled = True
table_header = [_("ID"), _("Date"), _("Channel"), _("Title"), _("URL"), _("Watched")]
column_filter = [ytcc_core.config.table_format.getboolean("ID"),
                 ytcc_core.config.table_format.getboolean("Date"),
                 ytcc_core.config.table_format.getboolean("Channel"),
                 ytcc_core.config.table_format.getboolean("Title"),
                 ytcc_core.config.table_format.getboolean("URL"),
                 ytcc_core.config.table_format.getboolean("Watched")]


class Command(NamedTuple):
    name: str
    shortcuts: List[str]
    help: str
    action: Callable[[], Any]


def update_all() -> None:
    print(_("Updating channels..."))
    ytcc_core.update_all()


def maybe_print_description(description: str) -> None:
    global description_enabled
    if description_enabled:
        columns = shutil.get_terminal_size().columns
        delimiter = "=" * columns
        lines = description.splitlines()

        print()
        print(_("Video description:"))
        print(delimiter)

        for line in lines:
            print(wrap.fill(line, width=columns))

        print(delimiter, end="\n\n")


def interactive_prompt(video: Video) -> bool:
    executed_cmd = False
    RETURN_VAL_HELP = 0
    RETURN_VAL_QUIT = 1

    def print_help() -> int:
        print()
        print(_("Available commands:"))
        for command in commands:
            print(f"{command.name:>20}  {command.shortcuts[0]:<2}  {command.help}")
        print()
        return RETURN_VAL_HELP

    commands = [
        Command("help", ["h"], _("print this help"), print_help),
        Command("yes", ["y", ""], _("play the video"), lambda: play(video, no_video)),
        Command("no", ["n"], _("do not play the video"), lambda: None),
        Command("mark", ["m"], _("mark the video watched without playing it"),
                lambda: ytcc_core.mark_watched([video.id])),
        Command("audio", ["a"], _("play only the audio track of the video"),
                lambda: play(video, True)),
        Command("download-video", ["dv"], _("download the video"),
                lambda: download([video.id], False)),
        Command("download-audio", ["da"], _("download the audio track of the video"),
                lambda: download([video.id], True)),
        Command("quit", ["q", "exit"], _("exit ytcc"), lambda: RETURN_VAL_QUIT),
    ]

    def completer(text: str, state: int) -> Optional[str]:
        options = [cmd[0] for cmd in commands if cmd[0].startswith(text)]
        if state < len(options):
            return options[state]
        return None

    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" ")
    readline.set_completer(completer)

    while not executed_cmd:
        try:
            question = (_('Play video "{video.title}" by "{video.channelname}"?')
                        .format(video=video))
            choice = input(question +
                           '\n[y(es)/n(o)/a(udio)/m(ark)/q(uit)/h(elp)] (Default: y) > ')
        except EOFError:
            print()
            return False

        executed_cmd = True
        invalid_cmd = True
        choice = choice.lower()

        for cmd in commands:
            if choice in (cmd.name, *cmd.shortcuts):
                result = cmd.action()
                if result == RETURN_VAL_QUIT:
                    return False
                if result == RETURN_VAL_HELP:
                    executed_cmd = False
                invalid_cmd = False
                break

        if invalid_cmd:
            print()
            print(_("'{cmd}' is an invalid command. Type 'help' for more info.\n")
                  .format(cmd=choice))
            executed_cmd = False

    return True


def play(video: Video, audio_only: bool) -> None:
    maybe_print_description(video.description)
    if not ytcc_core.play_video(video.id, audio_only):
        print()
        print(_("WARNING: The video player terminated with an error.\n"
                "         The last video is not marked as watched!"))
        print()


def prefix_codes(alphabet: Set[str], count: int) -> List[str]:
    codes = list(alphabet)

    if len(codes) < 2:
        raise ValueError("alphabet must have at least two characters")

    if count <= 0:
        raise ValueError("count must not be negative")

    if len(codes) >= count:
        return codes[:count]

    first = codes.pop(0)
    it = iter(alphabet)

    while len(codes) < count:
        try:
            char = next(it)
            codes.append(first + char)
        except StopIteration:
            it = iter(alphabet)
            first = codes.pop(0)
    return codes


def match_quickselect(tags: List[str], alphabet: Set[str]) -> str:
    def getch() -> str:
        """Read a single character from stdin without the need to press enter."""

        if not sys.stdin.isatty():
            return ""

        import tty
        import termios

        file_descriptor = sys.stdin.fileno()
        old_settings = termios.tcgetattr(file_descriptor)
        try:
            tty.setraw(sys.stdin.fileno())
            char = sys.stdin.read(1)
        finally:
            termios.tcsetattr(file_descriptor, termios.TCSADRAIN, old_settings)
        return char

    print()
    print(_("Type a valid TAG. <Ctrl+d> to exit. <Enter> accepts first video."))
    print("> ", end="", flush=True)

    tag = ""
    while tag not in tags:
        char = getch()

        if char in {"\x04", "\x03"}:  # Ctrl+d, Ctrl+d
            break

        if char in {"\r", ""}:
            tag = tags[0]
            break

        if char == "\x7f":  # DEL
            tag = tag[:-1]
        elif char in alphabet:
            tag += char

        # Clear line, reset cursor, print prompt and tag
        print("\033[2K\r>", tag, end="", flush=True)

    print()
    return tag


def watch(video_ids: Optional[Iterable[int]] = None) -> None:
    def print_title(video: Video) -> None:
        print(_('Playing "{video.title}" by "{video.channelname}"...').format(video=video))

    if not video_ids:
        videos = ytcc_core.list_videos()
        videos = sorted(videos, key=lambda v: v.publish_date)
    else:
        videos = ytcc_core.get_videos(video_ids)

    quickselect = ytcc_core.config.quickselect

    if not videos:
        print(_("No videos to watch. No videos match the given criteria."))
    elif not interactive_enabled:
        for v in videos:
            print_title(v)
            play(v, no_video)

    elif quickselect.enabled:
        alphabet = set(quickselect.alphabet)
        tags = prefix_codes(alphabet, len(videos))
        index = OrderedDict(zip(tags, videos))

        while index:
            remaining_tags = list(index.keys())
            remaining_videos = index.values()

            # Clear display and set cursor to (1,1). Allows scrolling back in some terminals
            print("\033[2J\033[1;1H", end="")
            print_videos(remaining_videos, quickselect_column=remaining_tags)

            tag = match_quickselect(remaining_tags, alphabet)
            video = index.get(tag)

            if video is None:
                break

            print()
            if quickselect.ask:
                if not interactive_prompt(video):
                    break
            else:
                print_title(video)
                play(video, no_video)

            del index[tag]

    else:
        for video in videos:
            if not interactive_prompt(video):
                break


def table_print(header: List[str], table: List[List[str]]) -> None:
    transposed = zip(header, *table)
    col_widths = [max(map(len, column)) for column in transposed]
    table_format = "│".join(itertools.repeat(" {{:<{}}} ", len(header))).format(*col_widths)

    if header_enabled:
        header_line = "┼".join("─" * (width + 2) for width in col_widths)
        print(table_format.format(*header))
        print(header_line)

    for row in table:
        print(table_format.format(*row))


def print_videos(videos: Iterable[Video],
                 quickselect_column: Optional[Iterable[str]] = None) -> None:
    def row_filter(row: Iterable[str]) -> List[str]:
        return list(itertools.compress(row, column_filter))

    def video_to_list(video: Video) -> List[str]:
        return [str(video.id), datetime.fromtimestamp(video.publish_date).strftime("%Y-%m-%d %H:%M"),
                video.channelname, video.title, ytcc_core.get_youtube_video_url(video.yt_videoid),
                _("Yes") if video.watched else _("No")]

    def concat_row(tag: str, video: Video) -> List[str]:
        row = row_filter(video_to_list(video))
        row.insert(0, tag)
        return row

    if quickselect_column is None:
        table = [row_filter(video_to_list(v)) for v in videos]
        table_print(row_filter(table_header), table)
    else:
        table = [concat_row(k, v) for k, v in zip(quickselect_column, videos)]
        header = row_filter(table_header)
        header.insert(0, "TAG")
        table_print(header, table)


def mark_watched(video_ids: Optional[List[int]]) -> None:
    marked_videos = ytcc_core.mark_watched(video_ids)
    if not marked_videos:
        print(_("No videos were marked as watched"))
    else:
        print(_("Following videos were marked as watched:"))
        print()
        print_videos(marked_videos)


def list_videos() -> None:
    videos = ytcc_core.list_videos()
    videos = sorted(videos, key=lambda v: v.publish_date)
    if not videos:
        print(_("No videos to list. No videos match the given criteria."))
    else:
        print_videos(videos)


def print_channels() -> None:
    channels = ytcc_core.get_channels()
    if not channels:
        print(_("No channels added, yet."))
    else:
        for channel in channels:
            print(channel.displayname)


def add_channel(name: str, channel_url: str) -> None:
    try:
        ytcc_core.add_channel(name, channel_url)
    except core.BadURLException:
        print(_("{!r} is not a valid YouTube URL").format(channel_url))
    except core.DuplicateChannelException:
        print(_("You are already subscribed to {!r}").format(name))
    except core.ChannelDoesNotExistException:
        print(_("The channel {!r} does not exist").format(channel_url))


def cleanup() -> None:
    print(_("Cleaning up database..."))
    ytcc_core.cleanup()


def import_channels(file: TextIO) -> None:
    print(_("Importing..."))
    try:
        ytcc_core.import_channels(file)
        subscriptions = _("Subscriptions")
        print()
        print(subscriptions)
        print("=" * len(subscriptions))
        print_channels()
    except core.InvalidSubscriptionFileError:
        print(_("The given file is not valid YouTube export file"))


def download(video_ids: Optional[List[int]], no_video: bool) -> None:
    stats = ytcc_core.download_videos(video_ids=video_ids, path=download_path,
                                      no_video=no_video)
    for id, success in stats:
        if success:
            ytcc_core.mark_watched([id])
        else:
            print(_("An Error occured while downloading the video"))


def run() -> None:
    args = arguments.get_args()
    option_executed = False

    if args.version:
        import ytcc
        print("ytcc version " + ytcc.__version__)
        print()
        print("Copyright (C) 2015-2018  " + ytcc.__author__)
        print("This program comes with ABSOLUTELY NO WARRANTY; This is free software, and you")
        print("are welcome to redistribute it under certain conditions.  See the GNU General ")
        print("Public Licence for details.")
        return

    if args.bug_report_info:
        import ytcc
        import youtube_dl.version
        import subprocess
        import feedparser
        import lxml.etree
        import dateutil
        print("---ytcc version---")
        print(ytcc.__version__)
        print()
        print("---youtube-dl version---")
        print(youtube_dl.version.__version__)
        print()
        print("---feedparser version---")
        print(feedparser.__version__)
        print()
        print("---lxml version---")
        print(lxml.etree.__version__)
        print()
        print("---dateutil version---")
        print(dateutil.__version__)
        print()
        print("---python version---")
        print(sys.version)
        print()
        print("---mpv version---")
        subprocess.run(["mpv", "--version"])
        print()
        print("---config dump---")
        print(ytcc_core.config)
        return

    if args.disable_interactive:
        global interactive_enabled
        interactive_enabled = False

    if args.no_description:
        global description_enabled
        description_enabled = False

    if args.no_header:
        global header_enabled
        header_enabled = False

    if args.no_video:
        global no_video
        no_video = True

    if args.path:
        global download_path
        download_path = args.path

    if args.include_watched:
        ytcc_core.set_include_watched_filter()
        global column_filter
        column_filter[5] = True

    if args.columns:
        if args.columns == ["all"]:
            column_filter = [True] * len(table_header)
        else:
            column_filter = [True if f in args.columns else False for f in table_header]

    if args.channel_filter:
        ytcc_core.set_channel_filter(args.channel_filter)

    if args.since:
        ytcc_core.set_date_begin_filter(args.since)

    if args.to:
        ytcc_core.set_date_end_filter(args.to)

    if args.search:
        ytcc_core.set_search_filter(args.search)

    if args.import_from:
        import_channels(args.import_from)
        option_executed = True

    if args.cleanup:
        cleanup()
        option_executed = True

    if args.add_channel:
        add_channel(*args.add_channel)
        option_executed = True

    if args.list_channels:
        print_channels()
        option_executed = True

    if args.delete_channel:
        ytcc_core.delete_channels(args.delete_channel)
        option_executed = True

    if args.update:
        if option_executed:
            print()
        update_all()
        option_executed = True

    if args.list:
        if option_executed:
            print()
        list_videos()
        option_executed = True

    if args.download is not None:
        if option_executed:
            print()
        download(args.download if args.download else None, no_video)
        option_executed = True

    if args.watch is not None:
        if option_executed:
            print()
        watch(args.watch)
        option_executed = True

    if args.mark_watched is not None:
        if option_executed:
            print()
        mark_watched(args.mark_watched if args.mark_watched else None)
        option_executed = True

    if not option_executed:
        update_all()
        print()
        if not ytcc_core.config.quickselect.enabled:
            list_videos()
            print()
        watch()


def register_signal_handlers() -> None:
    def handler(signum: Any, frame: Any) -> None:
        print()
        print(_("Bye..."))
        exit(1)

    signal.signal(signal.SIGINT, handler)


def main() -> None:
    register_signal_handlers()
    run()
