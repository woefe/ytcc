# ytcc - The YouTube channel checker
# Copyright (C) 2021  Wolfgang Popp
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

import sys
from enum import Enum
from typing import Optional

import click


class FKeys(str, Enum):
    """Indetifiers for special key sequences like the F-keys."""

    F1 = "<F1>"
    F2 = "<F2>"
    F3 = "<F3>"
    F4 = "<F4>"
    F5 = "<F5>"
    F6 = "<F6>"
    F7 = "<F7>"
    F8 = "<F8>"
    DEL = "DEL"


# https://invisible-island.net/xterm/xterm-function-keys.html
_KNOWN_KEYS = {
    # vt100
    "\x1bOP": FKeys.F1,
    "\x1bOQ": FKeys.F2,
    "\x1bOR": FKeys.F3,
    "\x1bOS": FKeys.F4,
    "\x1bOt": FKeys.F5,
    "\x1bOu": FKeys.F6,
    "\x1bOv": FKeys.F7,
    "\x1bOl": FKeys.F8,

    # rxvt
    "\x1b[11~": FKeys.F1,
    "\x1b[12~": FKeys.F2,
    "\x1b[13~": FKeys.F3,
    "\x1b[14~": FKeys.F4,
    "\x1b[15~": FKeys.F5,
    "\x1b[17~": FKeys.F6,
    "\x1b[18~": FKeys.F7,
    "\x1b[19~": FKeys.F8,

    # linux
    "\x1b[[A": FKeys.F1,
    "\x1b[[B": FKeys.F2,
    "\x1b[[C": FKeys.F3,
    "\x1b[[D": FKeys.F4,
    "\x1b[[E": FKeys.F5,

    # Windows
    "\x00;": FKeys.F1,
    "\x00<": FKeys.F2,
    "\x00=": FKeys.F3,
    "\x00>": FKeys.F4,
    "\x00?": FKeys.F5,
    "\x00@": FKeys.F6,
    "\x00A": FKeys.F7,
    "\x00B": FKeys.F8,

    # other
    "\x7f": FKeys.DEL,  # Linux
    "\x08": FKeys.DEL,  # Windows
}


def getkey() -> str:
    """Read a single character from stdin without the need to press enter.

    If the key press caused an escape sequence, return the sequence (see Keys). If the sequence
    could not be understood, return "Unknown Sequence".

    :return: Character read from stdin.
    """
    try:
        sequence = click.getchar()
    except EOFError:
        sequence = "\x04"

    key = _KNOWN_KEYS.get(sequence)
    if key is not None:
        return key

    if len(sequence) != 1:
        return "Unknown Sequence"

    return sequence


def clear_screen() -> None:
    """Clear the terminal.

    Resets the curser to (0,0).
    """
    click.clear()


def printtln(*text, foreground: Optional[int] = None, background: Optional[int] = None,
             bold: bool = False, replace: bool = False) -> None:
    """Like printt, but print newline at the end.

    :param text: The text to print, elements are concatenated without a separator.
    :param foreground: Foreground color.
    :param background: Background color.
    :param bold: Make text bold.
    :param replace: Replace the current line.
    """
    printt(*text, foreground=foreground, background=background, bold=bold, replace=replace)
    print()


def printt(*text, foreground: Optional[int] = None, background: Optional[int] = None,
           bold: bool = False, replace: bool = False) -> None:
    """Print text on terminal styled with ANSI escape sequences.

    If stdout is not a TTY, no escape sequences will be printed. Supports 8-bit colors.

    :param text: The text to print, elements are concatenated without a separator.
    :param foreground: Foreground color.
    :param background: Background color.
    :param bold: Make text bold.
    :param replace: Replace the current line.
    """
    if not sys.stdout.isatty():
        print(*text, sep="", end="", flush=True)
        return

    esc_color_background = "\033[48;5;{}m"
    esc_color_foreground = "\033[38;5;{}m"
    esc_clear_attrs = "\033[0m"
    esc_bold = "\033[1m"

    if foreground is not None and 0 <= foreground <= 255:
        print(esc_color_foreground.format(foreground), end="")

    if background is not None and 0 <= background <= 255:
        print(esc_color_background.format(background), end="")

    if bold:
        print(esc_bold, end="")

    if replace:
        print("\033[2K\r", end="")

    print(*text, sep="", end="")
    print(esc_clear_attrs, flush=True, end="")


def get_terminal_width() -> int:
    width, _ = click.get_terminal_size()
    return width
