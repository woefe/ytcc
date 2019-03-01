# ytcc - The YouTube channel checker
# Copyright (C) 2019  Wolfgang Popp
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

# Allow global statement
# pylint: disable=W0603

import itertools
import sys
from collections import OrderedDict

import inspect
import shutil
import signal
import textwrap as wrap
from datetime import datetime
from enum import Enum
from typing import List, Iterable, Optional, TextIO, Any, Set, Tuple, Callable, NamedTuple, Dict, \
    BinaryIO

from ytcc import core, arguments, terminal, _
from ytcc.database import Video
from ytcc.exceptions import BadConfigException, ChannelDoesNotExistException, \
    DuplicateChannelException, BadURLException
from ytcc.terminal import printt, printtln
from ytcc.utils import unpack_optional

try:
    ytcc_core = core.Ytcc()  # pylint: disable=C0103
    COLUMN_FILTER = [ytcc_core.config.table_format.getboolean("ID"),
                     ytcc_core.config.table_format.getboolean("Date"),
                     ytcc_core.config.table_format.getboolean("Channel"),
                     ytcc_core.config.table_format.getboolean("Title"),
                     ytcc_core.config.table_format.getboolean("URL"),
                     ytcc_core.config.table_format.getboolean("Watched")]
    COLORS = ytcc_core.config.color
except BadConfigException:
    print(_("The configuration file has errors!"))
    exit(1)

INTERACTIVE_ENABLED = True
DESCRIPTION_ENABLED = True
NO_VIDEO = False
DOWNLOAD_PATH = ""
HEADER_ENABLED = True
TABLE_HEADER = [_("ID"), _("Date"), _("Channel"), _("Title"), _("URL"), _("Watched")]
_REGISTERED_OPTIONS: Dict[str, "Option"] = dict()


def register_option(option_name, exit=False, is_action=True):  # pylint: disable=redefined-builtin
    def decorator(func):
        nargs = len(inspect.signature(func).parameters)
        _REGISTERED_OPTIONS[option_name] = Option(
            run=func, exit=exit, nargs=nargs, is_action=is_action)
        return func

    return decorator


class Option(NamedTuple):
    run: Callable
    exit: bool
    nargs: int
    is_action: bool


class Action(Enum):
    def __init__(self, text: str, hotkey: str, color: int):
        self.text = text
        self.hotkey = hotkey
        self.color = color

    SHOW_HELP = (None, terminal.Keys.F1, None)
    PLAY_VIDEO = (_("Play video"), terminal.Keys.F2, COLORS.prompt_play_video)
    PLAY_AUDIO = (_("Play audio"), terminal.Keys.F3, COLORS.prompt_play_audio)
    MARK_WATCHED = (_("Mark as watched"), terminal.Keys.F4, COLORS.prompt_mark_watched)
    REFRESH = (None, terminal.Keys.F5, None)
    DOWNLOAD_AUDIO = (_("Download audio"), terminal.Keys.F7, COLORS.prompt_download_audio)
    DOWNLOAD_VIDEO = (_("Download video"), terminal.Keys.F6, COLORS.prompt_download_video)


class Interactive:

    def __init__(self, videos: List[Video]):
        self.videos = videos
        self.previous_action = Action.PLAY_AUDIO if NO_VIDEO else Action.PLAY_VIDEO
        self.action = self.previous_action

        def makef(arg):
            return lambda: self.set_action(arg)

        self.hooks = {action.hotkey: makef(action) for action in list(Action)}

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
        iterator = iter(alphabet)

        while len(codes) < count:
            try:
                char = next(iterator)
                codes.append(first + char)
            except StopIteration:
                iterator = iter(alphabet)
                first = codes.pop(0)
        return codes

    def get_prompt_text(self) -> str:
        return self.action.text

    def get_prompt_color(self) -> Optional[int]:
        return self.action.color

    def command_line(self, tags: List[str], alphabet: Set[str]) -> Tuple[str, bool]:
        def print_prompt():
            prompt_format = "{prompt_text} > "
            prompt = prompt_format.format(prompt_text=self.get_prompt_text())
            printt(prompt, foreground=self.get_prompt_color(), bold=True, replace=True)

        print()
        print(_("Type a valid TAG. <F1> for help."))
        print_prompt()

        tag = ""
        hook_triggered = False
        while tag not in tags:
            char = terminal.getkey()

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

            print_prompt()
            printt(tag)

        print()
        return tag, hook_triggered

    def run(self) -> None:
        alphabet = ytcc_core.config.quickselect_alphabet
        tags = self._prefix_codes(alphabet, len(self.videos))
        index = OrderedDict(zip(tags, self.videos))

        while index:
            remaining_tags = list(index.keys())
            remaining_videos = index.values()

            # Clear display and set cursor to (1,1). Allows scrolling back in some terminals
            terminal.clear_screen()
            print_videos(remaining_videos, quickselect_column=remaining_tags)

            tag, hook_triggered = self.command_line(remaining_tags, alphabet)
            video = index.get(tag)

            if video is None and not hook_triggered:
                break

            if video is not None:
                if self.action is Action.MARK_WATCHED:
                    video.watched = True
                    del index[tag]
                elif self.action is Action.DOWNLOAD_AUDIO:
                    print()
                    download_video(video, True)
                    del index[tag]
                elif self.action is Action.DOWNLOAD_VIDEO:
                    print()
                    download_video(video, False)
                    del index[tag]
                elif self.action is Action.PLAY_AUDIO:
                    print()
                    play(video, True)
                    del index[tag]
                elif self.action is Action.PLAY_VIDEO:
                    print()
                    play(video, False)
                    del index[tag]
            elif self.action is Action.SHOW_HELP:
                self.action = self.previous_action
                terminal.clear_screen()
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
                input(_("Press Enter to continue"))
            elif self.action is Action.REFRESH:
                self.action = self.previous_action
                terminal.clear_screen()
                update_all()
                self.videos = ytcc_core.list_videos()
                self.run()
                break


def maybe_print_description(description: Optional[str]) -> None:
    if DESCRIPTION_ENABLED and description is not None:
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


def table_print(header: List[str], table: List[List[str]]) -> None:
    transposed = zip(header, *table)
    col_widths = [max(map(len, column)) for column in transposed]
    table_format = "│".join(itertools.repeat(" {{:<{}}} ", len(header))).format(*col_widths)

    if HEADER_ENABLED:
        header_line = "┼".join("─" * (width + 2) for width in col_widths)
        printtln(table_format.format(*header), bold=True)
        print(header_line)

    for i, row in enumerate(table):
        background = None if i % 2 == 0 else COLORS.table_alternate_background
        printtln(table_format.format(*row), background=background)


def print_videos(videos: Iterable[Video],
                 quickselect_column: Optional[Iterable[str]] = None) -> None:
    def row_filter(row: Iterable[str]) -> List[str]:
        return list(itertools.compress(row, COLUMN_FILTER))

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
        table_print(row_filter(TABLE_HEADER), table)
    else:
        table = [concat_row(k, v) for k, v in zip(quickselect_column, videos)]
        header = row_filter(TABLE_HEADER)
        header.insert(0, "TAG")
        table_print(header, table)


def download_video(video: Video, audio_only: bool = False) -> None:
    print(_('Downloading "{video.title}" by "{video.channel.displayname}"...').format(video=video))
    success = ytcc_core.download_video(video=video, path=DOWNLOAD_PATH, audio_only=audio_only)
    if not success:
        print(_("An Error occured while downloading the video"))


@register_option("mark_watched")
def mark_watched(video_ids: List[int]) -> None:
    ytcc_core.set_video_id_filter(video_ids)
    videos = ytcc_core.list_videos()
    if not videos:
        print(_("No videos were marked as watched"))
        return

    for video in videos:
        video.watched = True

    print(_("Following videos were marked as watched:"))
    print()
    print_videos(videos)


@register_option("watch")
def watch(video_ids: Iterable[int]) -> None:
    ytcc_core.set_video_id_filter(video_ids)
    videos = ytcc_core.list_videos()

    if not videos:
        print(_("No videos to watch. No videos match the given criteria."))
    elif not INTERACTIVE_ENABLED:
        for video in videos:
            play(video, NO_VIDEO)
    else:
        Interactive(videos).run()


@register_option("download")
def download(video_ids: List[int]) -> None:
    ytcc_core.set_video_id_filter(video_ids)
    for video in ytcc_core.list_videos():
        download_video(video, NO_VIDEO)


@register_option("update")
def update_all() -> None:
    print(_("Updating channels..."))
    ytcc_core.update_all()


@register_option("list")
def list_videos() -> None:
    videos = ytcc_core.list_videos()
    if not videos:
        print(_("No videos to list. No videos match the given criteria."))
    else:
        print_videos(videos)


@register_option("list_channels")
def print_channels() -> None:
    channels = ytcc_core.get_channels()
    if not channels:
        print(_("No channels added, yet."))
    else:
        for channel in channels:
            print(channel.displayname)


@register_option("add_channel", exit=True)
def add_channel(name: str, channel_url: str) -> None:
    try:
        ytcc_core.add_channel(name, channel_url)
    except BadURLException:
        print(_("{!r} is not a valid YouTube URL").format(channel_url))
    except DuplicateChannelException:
        print(_("You are already subscribed to {!r}").format(name))
    except ChannelDoesNotExistException:
        print(_("The channel {!r} does not exist").format(channel_url))


@register_option("delete_channel", exit=True)
def delete_channel(channels: List[str]) -> None:
    ytcc_core.delete_channels(channels)


@register_option("rename", exit=True)
def rename_channel(oldname: str, newname: str) -> None:
    try:
        ytcc_core.rename_channel(oldname, newname)
    except ChannelDoesNotExistException:
        print(_("Error: The given channel does not exist."))
    except DuplicateChannelException:
        print(_("Error: The new name already exists."))


@register_option("cleanup", exit=True)
def cleanup() -> None:
    print(_("Cleaning up database..."))
    ytcc_core.cleanup()


@register_option("import_from", exit=True)
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


@register_option("export_to", exit=True)
def export_channels(file: BinaryIO) -> None:
    ytcc_core.export_channels(file)


@register_option("version", exit=True)
def version() -> None:
    import ytcc
    print("ytcc version " + ytcc.__version__)
    print()
    print("Copyright (C) 2015-2019  " + ytcc.__author__)
    print("This program comes with ABSOLUTELY NO WARRANTY; This is free software, and you")
    print("are welcome to redistribute it under certain conditions.  See the GNU General ")
    print("Public Licence for details.")


@register_option("bug_report_info", exit=True)
def bug_report_info() -> None:
    import ytcc
    import youtube_dl.version
    import subprocess
    import feedparser
    import lxml.etree
    import sqlalchemy
    print("---ytcc version---")
    print(ytcc.__version__)
    print()
    print("---youtube-dl version---")
    print(youtube_dl.version.__version__)
    print()
    print("---SQLAlchemy version---")
    print(sqlalchemy.__version__)  # type: ignore
    print()
    print("---feedparser version---")
    print(feedparser.__version__)
    print()
    print("---lxml version---")
    print(lxml.etree.__version__)
    print()
    print("---python version---")
    print(sys.version)
    print()
    print("---mpv version---")
    subprocess.run(["mpv", "--version"])
    print()
    print("---config dump---")
    print(ytcc_core.config)


@register_option("disable_interactive", is_action=False)
def disable_interactive() -> None:
    global INTERACTIVE_ENABLED
    INTERACTIVE_ENABLED = False


@register_option("no_description", is_action=False)
def disable_description() -> None:
    global DESCRIPTION_ENABLED
    DESCRIPTION_ENABLED = False


@register_option("no_header", is_action=False)
def disable_header() -> None:
    global HEADER_ENABLED
    HEADER_ENABLED = False


@register_option("no_video", is_action=False)
def disable_video() -> None:
    global NO_VIDEO
    NO_VIDEO = True


@register_option("path", is_action=False)
def set_download_path(path: str) -> None:
    global DOWNLOAD_PATH
    DOWNLOAD_PATH = path


@register_option("columns", is_action=False)
def set_columns(cols: List["str"]) -> None:
    global COLUMN_FILTER
    if cols == ["all"]:
        COLUMN_FILTER = [True] * len(TABLE_HEADER)
    else:
        COLUMN_FILTER = [f in cols for f in TABLE_HEADER]


@register_option("include_watched", is_action=False)
def set_include_watched_filter() -> None:
    ytcc_core.set_include_watched_filter()
    COLUMN_FILTER[5] = True


@register_option("channel_filter", is_action=False)
def set_channel_filter(channels: List[str]) -> None:
    ytcc_core.set_channel_filter(channels)


@register_option("since", is_action=False)
def set_date_begin_filter(begin: datetime) -> None:
    ytcc_core.set_date_begin_filter(begin)


@register_option("to", is_action=False)
def set_date_end_filter(end: datetime) -> None:
    ytcc_core.set_date_end_filter(end)


def run() -> None:
    args = vars(arguments.get_args())
    option_names = [
        "version", "bug_report_info", "add_channel", "delete_channel", "cleanup", "import_from",
        "export_to", "rename",

        "disable_interactive", "no_description", "no_header", "no_video", "path",
        "include_watched", "columns", "channel_filter", "since", "to", "list_channels", "update",
        "list", "download", "watch", "mark_watched"
    ]

    action_executed = False
    for option_name in option_names:
        option = _REGISTERED_OPTIONS.get(option_name)
        arg = args.get(option_name)
        if option is not None and (arg or arg == []):
            if option.nargs == 0:
                option.run()
            elif option.nargs == 1:
                option.run(arg)
            else:
                option.run(*arg)

            action_executed = action_executed or option.is_action

            if option.exit:
                return

    if not action_executed:
        update_all()
        print()
        if not INTERACTIVE_ENABLED:
            list_videos()
            print()
        watch([])


def register_signal_handlers() -> None:
    # pylint: disable=unused-argument
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
