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

import sys
import tty
import termios

from typing import Optional


class Keys:
    """Indetifiers for special key sequences like the F-keys."""

    F1 = "<F1>"
    F2 = "<F2>"
    F3 = "<F3>"
    F4 = "<F4>"
    F5 = "<F5>"
    F6 = "<F6>"
    F7 = "<F7>"


# https://invisible-island.net/xterm/xterm-function-keys.html
_KNOWN_KEYS = {
    # vt100
    "\x1bOP": Keys.F1,
    "\x1bOQ": Keys.F2,
    "\x1bOR": Keys.F3,
    "\x1bOS": Keys.F4,
    "\x1bOt": Keys.F5,
    "\x1bOu": Keys.F6,
    "\x1bOv": Keys.F7,

    # rxvt
    "\x1b[11~": Keys.F1,
    "\x1b[12~": Keys.F2,
    "\x1b[13~": Keys.F3,
    "\x1b[14~": Keys.F4,
    "\x1b[15~": Keys.F5,
    "\x1b[17~": Keys.F6,
    "\x1b[18~": Keys.F7,

    # linux
    "\x1b[[A": Keys.F1,
    "\x1b[[B": Keys.F2,
    "\x1b[[C": Keys.F3,
    "\x1b[[D": Keys.F4,
    "\x1b[[E": Keys.F5,
}

_PREFIXES = {
    escape_sequence[:i]
    for escape_sequence in _KNOWN_KEYS
    for i in range(1, len(escape_sequence) + 1)
}


def _read_sequence(stream) -> str:
    seq = stream.read(1)
    if seq == "\x1b":
        while seq not in _KNOWN_KEYS and seq in _PREFIXES:
            seq += stream.read(1)

        return _KNOWN_KEYS.get(seq, "Unknown Sequence")

    return seq


def getkey() -> str:
    """Read a single character from stdin without the need to press enter.

    If the key press caused an escape sequence, return the sequence (see Keys). If the sequence
    could not be understood, return "Unknown Sequence".

    :return: Character read from stdin.
    """
    if not sys.stdin.isatty():
        return ""

    file_descriptor = sys.stdin.fileno()
    old_settings = termios.tcgetattr(file_descriptor)
    try:
        tty.setraw(sys.stdin.fileno())
        char = _read_sequence(sys.stdin)
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, old_settings)
    return char


def clear_screen() -> None:
    print("\033[2J\033[1;1H", end="")


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
        print(*text, sep="", end="")
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
        print(f"\033[2K\r", end="")

    print(*text, sep="", end="")
    print(esc_clear_attrs, flush=True, end="")
