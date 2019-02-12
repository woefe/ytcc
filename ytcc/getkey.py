import sys
import tty
import termios


class Keys:
    F1 = "<F1>"
    F2 = "<F2>"
    F3 = "<F3>"
    F4 = "<F4>"
    F5 = "<F5>"
    F6 = "<F6>"
    F7 = "<F7>"


# https://invisible-island.net/xterm/xterm-function-keys.html
_known_keys = {
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

_prefixes = set()
for seq in _known_keys.keys():
    for i in range(1, len(seq) + 1):
        _prefixes.add(seq[:i])


def _read_sequence(fd) -> str:
    seq = fd.read(1)
    if seq == "\x1b":
        while seq not in _known_keys and seq in _prefixes:
            seq += fd.read(1)

        return _known_keys.get(seq, "Unknown Sequence")
    else:
        return seq


def getkey() -> str:
    """Read a single character from stdin without the need to press enter."""

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
