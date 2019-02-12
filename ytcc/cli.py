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
import sys
from collections import OrderedDict

import shutil
import signal
import textwrap as wrap
from datetime import datetime
from enum import Enum
from gettext import gettext as _
from typing import List, Iterable, Optional, TextIO, Any, Set, Tuple

from ytcc import core, arguments
from ytcc.db import Video
from ytcc.utils import unpack_optional

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


class Action(Enum):
    PLAY_VIDEO = 1
    PLAY_AUDIO = 2
    DOWNLOAD_VIDEO = 3
    DOWNLOAD_AUDIO = 4
    MARK_WATCHED = 5
    SHOW_HELP = 6
    REFRESH = 7


class Interactive:

    def __init__(self, videos: List[Video]):
        self.videos = videos
        self.previous_action = Action.PLAY_VIDEO
        self.action = Action.PLAY_VIDEO
        self.hooks = {
            "<F1>": lambda: self.set_action(Action.SHOW_HELP),
            "<F2>": lambda: self.set_action(Action.PLAY_VIDEO),
            "<F3>": lambda: self.set_action(Action.PLAY_AUDIO),
            "<F4>": lambda: self.set_action(Action.MARK_WATCHED),
            "<F5>": lambda: self.set_action(Action.REFRESH),
            "<F6>": lambda: self.set_action(Action.DOWNLOAD_VIDEO),
            "<F7>": lambda: self.set_action(Action.DOWNLOAD_AUDIO),
        }

    def set_action(self, action: Action) -> bool:
        self.previous_action = self.action
        self.action = action
        return action in (Action.SHOW_HELP, Action.REFRESH)

    @staticmethod
    def _prefix_codes(alphabet: Set[str], count: int) -> List[str]:
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

    @staticmethod
    def read_sequence(fd) -> str:
        f_keys = {
            "\x1bOP": "<F1>",
            "\x1bOQ": "<F2>",
            "\x1bOR": "<F3>",
            "\x1bOS": "<F4>",
            "\x1b[15~": "<F5>",
            "\x1b[17~": "<F6>",
            "\x1b[18~": "<F7>",
        }
        seq = fd.read(1)
        if seq == "\x1b":
            seq += fd.read(1)
            if seq == "\x1bO":
                seq += sys.stdin.read(1)
            elif seq == "\x1b[":
                b = sys.stdin.read(1)
                while b != "~":
                    seq += b
                    b = sys.stdin.read(1)
                seq += b
            return f_keys.get(seq, "Unknown Sequence")
        else:
            return seq

    def getch(self) -> str:
        """Read a single character from stdin without the need to press enter."""

        if not sys.stdin.isatty():
            return ""

        import tty
        import termios

        file_descriptor = sys.stdin.fileno()
        old_settings = termios.tcgetattr(file_descriptor)
        try:
            tty.setraw(sys.stdin.fileno())
            char = self.read_sequence(sys.stdin)
        finally:
            termios.tcsetattr(file_descriptor, termios.TCSADRAIN, old_settings)
        return char

    def get_prompt_text(self) -> str:
        if self.action == Action.MARK_WATCHED:
            return _("Mark as watched")
        if self.action == Action.DOWNLOAD_AUDIO:
            return _("Download audio")
        if self.action == Action.DOWNLOAD_VIDEO:
            return _("Download video")
        if self.action == Action.PLAY_AUDIO:
            return _("Play audio")
        if self.action == Action.PLAY_VIDEO:
            return _("Play video")

        return ""

    def command_line(self, tags: List[str], alphabet: Set[str]) -> Tuple[str, bool]:
        prompt_format = "{prompt_text} >"
        prompt = prompt_format.format(prompt_text=self.get_prompt_text())
        print()
        print(_("Type a valid TAG. <F1> for help."))
        print(prompt, end=" ", flush=True)

        tag = ""
        hook_triggered = False
        while tag not in tags:
            char = self.getch()

            if char in self.hooks:
                hook_triggered = True
                if self.hooks[char]():
                    break

            if char in {"\x04", "\x03"}:  # Ctrl+d, Ctrl+d
                break

            if char in {"\r", ""}:
                tag = tags[0]
                break

            if char == "\x7f":  # DEL
                tag = tag[:-1]
            elif char in alphabet:
                tag += char

            prompt = prompt_format.format(prompt_text=self.get_prompt_text())
            # Clear line, reset cursor, print prompt and tag
            print(f"\033[2K\r{prompt}", tag, end="", flush=True)

        print()
        return tag, hook_triggered

    def run(self) -> None:
        alphabet = set(ytcc_core.config.quickselect_alphabet)
        tags = self._prefix_codes(alphabet, len(self.videos))
        index = OrderedDict(zip(tags, self.videos))

        while index:
            remaining_tags = list(index.keys())
            remaining_videos = index.values()

            # Clear display and set cursor to (1,1). Allows scrolling back in some terminals
            print("\033[2J\033[1;1H", end="")
            print_videos(remaining_videos, quickselect_column=remaining_tags)

            tag, hook_triggered = self.command_line(remaining_tags, alphabet)
            video = index.get(tag)

            if video is None and not hook_triggered:
                break

            if video is not None:
                if self.action == Action.MARK_WATCHED:
                    video.watched = True
                    del index[tag]
                elif self.action == Action.DOWNLOAD_AUDIO:
                    print()
                    download_video(video, True)
                    del index[tag]
                elif self.action == Action.DOWNLOAD_VIDEO:
                    print()
                    download_video(video, False)
                    del index[tag]
                elif self.action == Action.PLAY_AUDIO:
                    print()
                    play(video, True)
                    del index[tag]
                elif self.action == Action.PLAY_VIDEO:
                    print()
                    play(video, False)
                    del index[tag]
            elif self.action == Action.SHOW_HELP:
                self.action = self.previous_action
                print("\033[2J\033[1;1H", end="")
                print(_(
                    "    <F1> Display this help text.\n"
                    "    <F2> Set action: Play video.\n"
                    "    <F3> Set action: Play audio.\n"
                    "    <F4> Set action: Mark as watched.\n"
                    "    <F5> Refresh video list.\n"
                    "    <F6> Set action: Download video.\n"
                    "    <F7> Set action: Download audio.\n"
                    " <Enter> Accept first video.\n"
                    "<CTRL+D> Exit.\n"
                ))
                input("Press Enter to continue")
            elif self.action == Action.REFRESH:
                self.action = self.previous_action
                print("\033[2J\033[1;1H", end="")
                update_all()
                self.videos = ytcc_core.list_videos()
                self.run()
                break


def update_all() -> None:
    print(_("Updating channels..."))
    ytcc_core.update_all()


def maybe_print_description(description: Optional[str]) -> None:
    global description_enabled
    if description_enabled and description is not None:
        columns = shutil.get_terminal_size().columns
        delimiter = "=" * columns
        lines = description.splitlines()

        print()
        print(_("Video description:"))
        print(delimiter)

        for line in lines:
            print(wrap.fill(line, width=columns))

        print(delimiter, end="\n\n")


def play(video: Video, audio_only: bool) -> None:
    print(_('Playing "{video.title}" by "{video.channel.displayname}"...').format(video=video))
    maybe_print_description(video.description)
    if not ytcc_core.play_video(video, audio_only):
        print()
        print(_("WARNING: The video player terminated with an error.\n"
                "         The last video is not marked as watched!"))
        print()


def watch(video_ids: Optional[Iterable[int]] = None) -> None:
    ytcc_core.set_video_id_filter(video_ids)
    videos = ytcc_core.list_videos()

    if not videos:
        print(_("No videos to watch. No videos match the given criteria."))
    elif not interactive_enabled:
        for v in videos:
            play(v, no_video)
    else:
        Interactive(videos).run()


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
        timestamp = unpack_optional(video.publish_date, lambda: 0)
        return [
            str(video.id),
            datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M"),
            str(video.channel.displayname),
            str(video.title),
            ytcc_core.get_youtube_video_url(video.yt_videoid),
            _("Yes") if video.watched else _("No")
        ]

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
    ytcc_core.set_video_id_filter(video_ids)
    videos = ytcc_core.list_videos()
    if not videos:
        print(_("No videos were marked as watched"))
        return

    for v in videos:
        v.watched = True

    print(_("Following videos were marked as watched:"))
    print()
    print_videos(videos)


def list_videos() -> None:
    videos = ytcc_core.list_videos()
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


def download_video(video: Video, audio_only: bool = False) -> None:
    print(_('Downloading "{video.title}" by "{video.channel.displayname}"...').format(video=video))
    success = ytcc_core.download_video(video=video, path=download_path, audio_only=audio_only)
    if not success:
        print(_("An Error occured while downloading the video"))


def download(video_ids: Optional[List[int]] = None) -> None:
    ytcc_core.set_video_id_filter(video_ids)
    for video in ytcc_core.list_videos():
        download_video(video, no_video)


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
        download(args.download if args.download else None)
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
        if not interactive_enabled:
            list_videos()
            print()
        watch()


def register_signal_handlers() -> None:
    def handler(signum: Any, frame: Any) -> None:
        ytcc_core.close()
        print()
        print(_("Bye..."))
        exit(1)

    signal.signal(signal.SIGINT, handler)


def main() -> None:
    register_signal_handlers()
    run()
    ytcc_core.close()
