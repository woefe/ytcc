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

import shutil
import sys
import textwrap as wrap
from enum import Enum
from typing import Callable, NamedTuple, Optional, TextIO

from ytcc import config, terminal
from ytcc.core import Ytcc
from ytcc.database import MappedVideo
from ytcc.printer import Table, TableData, TablePrinter, VideoPrintable
from ytcc.terminal import FKeys, printt, printtln


class Option(NamedTuple):
    run: Callable
    exit: bool
    nargs: int
    is_action: bool


class Action(Enum):
    def __init__(self, text: str, hotkey: str, color: Callable[[], int]):
        self.text = text
        self.hotkey = hotkey
        self.color = color

    @staticmethod
    def from_config():
        return Action.__dict__.get(config.tui.default_action.value.upper(), Action.PLAY_VIDEO)

    SHOW_HELP = (None, FKeys.F1, None)
    PLAY_VIDEO = ("Play video", FKeys.F2, lambda: config.theme.prompt_play_video)
    PLAY_AUDIO = ("Play audio", FKeys.F3, lambda: config.theme.prompt_play_audio)
    MARK_WATCHED = (
        "Mark as watched",
        FKeys.F4,
        lambda: config.theme.prompt_mark_watched,
    )
    REFRESH = (None, FKeys.F5, None)
    DOWNLOAD_AUDIO = (
        "Download audio",
        FKeys.F7,
        lambda: config.theme.prompt_download_audio,
    )
    DOWNLOAD_VIDEO = (
        "Download video",
        FKeys.F6,
        lambda: config.theme.prompt_download_video,
    )
    UNMARK = (None, FKeys.F8, None)


class VideoSelection(TableData, dict):
    def __init__(self, alphabet: str, videos: list[MappedVideo]):
        super().__init__()
        codes = self._prefix_codes(frozenset(alphabet), len(videos))
        for code, video in zip(codes, videos):
            self[code] = video

    @staticmethod
    def _prefix_codes(alphabet: frozenset[str], count: int) -> list[str]:
        codes = list(alphabet)

        if len(codes) < 2:  # noqa: PLR2004
            raise ValueError("alphabet must have at least two characters")

        if count < 0:
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

    def table(self) -> Table:
        table = VideoPrintable(self.values()).table()
        data = [[code, *row] for code, row in zip(self.keys(), table.data)]
        return Table(["TAG", *table.header], data)


class Interactive:
    def __init__(self, core: Ytcc):
        self.core = core
        self.videos = list(core.list_videos())
        self.previous_action = Action.from_config()
        self.action = self.previous_action

        def makef(arg):
            return lambda: self.set_action(arg)

        self.hooks = {action.hotkey: makef(action) for action in list(Action)}

    def set_action(self, action: Action) -> bool:
        self.previous_action = self.action
        self.action = action
        return action in (Action.SHOW_HELP, Action.REFRESH, Action.UNMARK)

    def get_prompt_text(self) -> str:
        return self.action.text

    def get_prompt_color(self) -> Optional[int]:
        return self.action.color()

    def command_line(self, tags: list[str]) -> tuple[str, bool]:
        def print_prompt():
            prompt_format = "{prompt_text} > "
            prompt = prompt_format.format(prompt_text=self.get_prompt_text())
            printt(prompt, foreground=self.get_prompt_color(), bold=True, replace=True)

        print()
        print("Type a valid TAG. <F1> for help.")
        print_prompt()

        tag = ""
        hook_triggered = False
        while tag not in tags:
            char: Optional[str] = terminal.getkey()

            if char in self.hooks:
                hook_triggered = True
                if self.hooks[char]():
                    break

                char = None

            if char in {"\x04", "\x03"}:  # Ctrl+d, Ctrl+d
                hook_triggered = False
                break

            if char in {"\r", ""} and tags:
                tag = tags[0]
                break

            if char == FKeys.DEL:
                tag = tag[:-1]
            elif char and char in config.tui.alphabet:
                tag += char

            print_prompt()
            printt(tag)

        print()
        return tag, hook_triggered

    def run(self) -> None:
        selectable = VideoSelection(config.tui.alphabet, self.videos)
        printer = TablePrinter()
        printer.filter = ["TAG", *config.ytcc.video_attrs]

        while True:
            remaining_tags = list(selectable.keys())

            # Clear display and set cursor to (1,1). Allows scrolling back in some terminals
            terminal.clear_screen()
            printer.print(selectable)

            tag, hook_triggered = self.command_line(remaining_tags)
            video = selectable.get(tag)

            if video is None and not hook_triggered:
                break

            actions: dict[Action, Callable[[MappedVideo], Optional[bool]]] = {
                Action.MARK_WATCHED: self.core.mark_watched,
                Action.DOWNLOAD_AUDIO: lambda v: self.download_video(v, True),
                Action.DOWNLOAD_VIDEO: lambda v: self.download_video(v, False),
                Action.PLAY_AUDIO: lambda v: self.play(v, True),
                Action.PLAY_VIDEO: lambda v: self.play(v, False),
            }

            if (
                video is not None
                and self.action in actions
                and actions[self.action](video) in [True, None]
            ):
                del selectable[tag]

            elif self.action is Action.SHOW_HELP:
                self.action = self.previous_action
                terminal.clear_screen()
                print(
                    "    <F1> Display this help text.\n"
                    "    <F2> Set action: Play video.\n"
                    "    <F3> Set action: Play audio.\n"
                    "    <F4> Set action: Mark as watched.\n"
                    "    <F5> Refresh video list.\n"
                    "    <F6> Set action: Download video.\n"
                    "    <F7> Set action: Download audio.\n"
                    "    <F8> Mark most recent video as unwatched.\n"
                    " <Enter> Accept first video.\n"
                    "<CTRL+D> Exit.\n"
                )
                input("Press Enter to continue")
            elif self.action is Action.UNMARK:
                self.action = self.previous_action
                self.core.unmark_recent()
                self.videos = list(self.core.list_videos())
                self.run()
                break
            elif self.action is Action.REFRESH:
                self.action = self.previous_action
                terminal.clear_screen()
                self.core.update()
                self.videos = list(self.core.list_videos())
                self.run()
                break

    def play(self, video: MappedVideo, audio_only: bool) -> bool:
        print_meta(video)
        if self.core.play_video(video, audio_only):
            self.core.mark_watched(video)
            return True

        print(
            "The video player terminated with an error. The last video is not marked as watched!"
        )
        return False

    def download_video(self, video: MappedVideo, audio_only: bool = False) -> bool:
        playlists = ", ".join(v.name for v in video.playlists)
        print(f'Downloading "{video.title}" in playlist(s) "{playlists}"...')

        if self.core.download_video(video=video, audio_only=audio_only):
            self.core.mark_watched(video)
            return True

        print("An Error occurred while downloading the video")
        return False


class StdOutOverride:
    def __init__(self, stream):
        self.orig = sys.stdout
        self.stream = stream

    def __enter__(self):
        sys.stdout = self.stream
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.orig


def print_meta(video: MappedVideo, stream: TextIO = sys.stdout) -> None:
    with StdOutOverride(stream):

        def print_separator(text: Optional[str] = None, fat: bool = False) -> None:
            columns = shutil.get_terminal_size().columns
            sep = "━" if fat else "─"
            if not text:
                print(sep * columns)
            else:
                sep_len = columns - len(text) - 2
                padding = sep_len // 2
                printt(sep * padding)
                printt(" ", text, " ", bold=fat)
                printtln(sep * (padding + (sep_len % 2)))

        print_separator("Playing now", fat=True)
        printt("         Title: ")
        printtln(video.title, bold=True)
        printt("In playlist(s): ")
        printtln(", ".join(v.name for v in video.playlists), bold=True)

        description = video.description
        if description is not None:
            columns = shutil.get_terminal_size().columns
            lines = description.splitlines()
            print_separator("Video description")

            for line in lines:
                print(wrap.fill(line, width=columns))

        print_separator(fat=True)
        print()
