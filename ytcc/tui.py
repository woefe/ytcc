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

import inspect
import shutil
import sys
import textwrap as wrap
from collections import OrderedDict
from enum import Enum
from typing import List, Optional, Set, Tuple, Callable, NamedTuple, Dict

from ytcc import core, terminal, _
from ytcc.database import Video, MappedVideo
from ytcc.exceptions import BadConfigException
from ytcc.terminal import printt, printtln

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
    sys.exit(1)

INTERACTIVE_ENABLED = True
DESCRIPTION_ENABLED = True
NO_VIDEO = False
DOWNLOAD_PATH = ""
HEADER_ENABLED = True
TABLE_HEADER = [_("ID"), _("Date"), _("Channel"), _("Title"), _("URL"), _("Watched")]


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

    @staticmethod
    def from_config():
        return Action.__dict__.get(ytcc_core.config.default_action, Action.PLAY_VIDEO)

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
        self.previous_action = Action.PLAY_AUDIO if NO_VIDEO else Action.from_config()
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


def print_meta(video: MappedVideo) -> None:
    def print_separator(text: Optional[str] = None, fat: bool = False) -> None:
        columns = shutil.get_terminal_size().columns
        sep = "━" if fat else "─"
        if not text:
            print(sep * columns)
        else:
            sep_len = (columns - len(text) - 2)
            padding = sep_len // 2
            printt(sep * padding)
            printt(" ", text, " ", bold=fat)
            printtln(sep * (padding + (sep_len % 2)))

    print_separator("Playing now", fat=True)
    printt(_("Title:   "))
    printtln(video.title, bold=True)
    printt(_("Channel: "))
    printtln(video.playlists, bold=True)

    description = video.description
    if DESCRIPTION_ENABLED and description is not None:
        columns = shutil.get_terminal_size().columns
        lines = description.splitlines()
        print_separator(_("Video description"))

        for line in lines:
            print(wrap.fill(line, width=columns))

    print_separator(fat=True)
    print()


def play(video: Video, audio_only: bool) -> None:
    print_meta(video)
    if not ytcc_core.play_video(video, audio_only):
        print()
        print(_("WARNING: The video player terminated with an error.\n"
                "         The last video is not marked as watched!"))
        print()


def download_video(video: Video, audio_only: bool = False) -> None:
    print(_('Downloading "{video.title}" by "{video.channel.displayname}"...').format(video=video))
    success = ytcc_core.download_video(video=video, path=DOWNLOAD_PATH, audio_only=audio_only)
    if not success:
        print(_("An Error occured while downloading the video"))


