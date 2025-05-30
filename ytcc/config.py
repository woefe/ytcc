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

import configparser
import functools
import io
import locale
import logging
import os
import typing
from collections.abc import Callable, Sequence
from enum import Enum
from pathlib import Path
from typing import Any, TextIO

from ytcc.exceptions import BadConfigError
from ytcc.terminal import COLOR_MAX, COLOR_MIN

# typing.get_args and typing.get_origin were introduced in 3.8
if hasattr(typing, "get_args"):
    get_type_args = typing.get_args  # type: ignore[attr-defined]
else:

    def get_type_args(typ):
        return typ.__args__ if hasattr(typ, "__args__") else None


if hasattr(typing, "get_origin"):
    get_type_origin = typing.get_origin  # type: ignore[attr-defined]
else:

    def get_type_origin(typ):
        return typ.__origin__ if hasattr(typ, "__origin__") else None


logger = logging.getLogger(__name__)

_BOOLEAN_STATES = {
    "1": True,
    "yes": True,
    "true": True,
    "on": True,
    "0": False,
    "no": False,
    "false": False,
    "off": False,
}


class Color(int):
    def __new__(cls, val):
        i = super().__new__(cls, val)
        if COLOR_MIN >= i >= COLOR_MAX:
            raise ValueError(
                f"{val} is not a valid color. Must be in greater than 0 and less than 255"
            )
        return i


class Action(str, Enum):
    PLAY_VIDEO = "play_video"
    PLAY_AUDIO = "play_audio"
    MARK_WATCHED = "mark_watched"
    DOWNLOAD_AUDIO = "download_audio"
    DOWNLOAD_VIDEO = "download_video"


class VideoAttr(str, Enum):
    ID = "id"
    URL = "url"
    TITLE = "title"
    DESCRIPTION = "description"
    PUBLISH_DATE = "publish_date"
    WATCHED = "watched"
    DURATION = "duration"
    THUMBNAIL_URL = "thumbnail_url"
    EXTRACTOR_HASH = "extractor_hash"
    PLAYLISTS = "playlists"

    @staticmethod
    def from_str(string: str) -> "VideoAttr":
        v_attr = VideoAttr.__members__.get(string.upper())
        if v_attr is not None:
            return v_attr
        raise ValueError(f"{string} cannot be converted to VideoAttr")


class PlaylistAttr(str, Enum):
    NAME = "name"
    URL = "url"
    TAGS = "tags"
    REVERSE = "reverse"

    @staticmethod
    def from_str(string: str) -> "PlaylistAttr":
        p_attr = PlaylistAttr.__members__.get(string.upper())
        if p_attr is not None:
            return p_attr
        raise ValueError(f"{string} cannot be converted to PlaylistAttr")


class Direction(str, Enum):
    ASC = "asc"
    DESC = "desc"


class DateFormatStr(str):
    __slots__ = ()

    def __new__(cls, *arg):
        datechars = "aAwdbBmyYjUWx%"
        iterator = iter(arg[0])

        char = next(iterator, "")
        while char:
            if char == "%":
                next_char = next(iterator, "$")
                if next_char not in datechars:
                    raise ValueError(f"Invalid date format specifier '%{next_char}'")
            char = next(iterator, "")

        return super().__new__(cls, *arg)


class BaseConfig:
    def __setattr__(self, key, value):
        raise AttributeError("Attribute is immutable")


class ytcc(BaseConfig):
    download_dir: str = "~/Downloads"
    download_subdirs: bool = False
    mpv_flags: str = "--really-quiet --ytdl --ytdl-format=bestvideo[height<=?1080]+bestaudio/best"
    order_by: list[tuple[VideoAttr, Direction]] = [
        (VideoAttr.PLAYLISTS, Direction.ASC),
        (VideoAttr.PUBLISH_DATE, Direction.DESC),
    ]
    video_attrs: list[VideoAttr] = [
        VideoAttr.ID,
        VideoAttr.TITLE,
        VideoAttr.PUBLISH_DATE,
        VideoAttr.DURATION,
        VideoAttr.PLAYLISTS,
    ]
    playlist_attrs: list[PlaylistAttr] = list(PlaylistAttr)
    db_path: str = "~/.local/share/ytcc/ytcc.db"
    date_format: DateFormatStr = DateFormatStr("%Y-%m-%d")
    max_update_fail: int = 5
    max_update_backlog: int = 20
    age_limit: int = 0
    skip_live_stream: bool = True
    skip_non_public: bool = True


class tui(BaseConfig):
    alphabet: str = "sdfervghnuiojkl"
    default_action: Action = Action.PLAY_VIDEO


class theme(BaseConfig):
    prompt_download_audio: Color = Color(2)
    prompt_download_video: Color = Color(4)
    prompt_play_audio: Color = Color(2)
    prompt_play_video: Color = Color(4)
    prompt_mark_watched: Color = Color(1)
    table_alternate_background: Color = Color(245)
    plain_label_text: Color = Color(244)


class youtube_dl(BaseConfig):
    format: str = "bestvideo[height<=?1080]+bestaudio/best"
    output_template: str = "%(title)s.%(ext)s"
    ratelimit: int = 0
    retries: int = 0
    subtitles: list[str] = ["off"]
    thumbnail: bool = True
    merge_output_format: str = "mkv"
    max_duration: int = 0
    restrict_filenames: bool = False


def _get_config(override_cfg_file: str | None = None) -> configparser.ConfigParser:
    """Read config file from several locations.

    Searches at following locations:
    1. ``override_cfg_file``
    3. ``~/.ytcc.conf``
    4. ``$XDG_CONFIG_HOME/ytcc/ytcc.conf`` or ``~/.config/ytcc/ytcc.conf``
    5. ``/etc/ytcc/ytcc.conf``

    If no config file is found in these three locations, a default config file is created in
    ``$XDG_CONFIG_HOME/ytcc/ytcc.conf`` or ``~/.config/ytcc/ytcc.conf``.

    :param override_cfg_file: Read the config from this file.
    :return: The dict-like config object
    """
    config = configparser.ConfigParser(interpolation=None)

    config_home = os.getenv("XDG_CONFIG_HOME", "~/.config")
    default_cfg_file = Path(config_home, "ytcc/ytcc.conf").expanduser()

    cfg_file_locations = [
        Path("/etc/ytcc/ytcc.conf"),
        default_cfg_file,
        Path.home() / ".ytcc.conf",
    ]
    if override_cfg_file:
        cfg_file_locations.append(Path(override_cfg_file))

    encoding = locale.getpreferredencoding(False) or "utf-8"

    logger.debug("Trying to read config from following locations: %s", cfg_file_locations)
    readable_locations = config.read(cfg_file_locations, encoding=encoding)
    logger.debug("Config was read from following locations: %s", readable_locations)

    if not readable_locations:
        logger.debug("No config file found. Creating new config at %s", default_cfg_file)
        path = Path(default_cfg_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        with path.open("w", encoding=encoding) as conf_file:
            dump(conf_file)

    return config


def _enum_from_str(e_class: type[Enum], str_val: str) -> Enum:
    field: Any
    for field in e_class:
        # Might also raise a ValueError
        converted_val = _convert(field.value.__class__, str_val)
        if field.value == converted_val:
            return field

    raise ValueError(f"{str_val} is not a valid {e_class}")


def _bool_from_str(string: str) -> bool:
    bool_state = _BOOLEAN_STATES.get(string.lower())
    if bool_state is None:
        raise ValueError(f"{string} cannot be converted to bool")
    return bool_state


def _list_from_str(elem_type: type, list_str: str) -> list[Any]:
    return [_convert(elem_type, elem.strip()) for elem in list_str.split(",")]


def _tuple_from_str(types: Sequence[type], tuple_str) -> tuple:
    elems = tuple_str.split(":")
    if len(elems) != len(types):
        raise ValueError(f"{tuple_str} cannot be converted to tuple of type {types}")

    return tuple(_convert(typ, elem) for elem, typ in zip(elems, types, strict=False))


def _convert(typ: type[Any], string: str) -> Any:
    if get_type_origin(typ) is list:
        elem_conv = get_type_args(typ)[0]
        from_str: Callable[[str], Any] = functools.partial(_list_from_str, elem_conv)
    elif get_type_origin(typ) is tuple:
        from_str = functools.partial(_tuple_from_str, get_type_args(typ))
    elif issubclass(typ, Enum):
        from_str = functools.partial(_enum_from_str, typ)
    elif issubclass(typ, bool):
        from_str = _bool_from_str
    elif next((c for c in (int, float, str) if issubclass(typ, c)), None):
        from_str = typ
    else:
        raise TypeError(f"Unsupported config parameter type in {typ}")

    return from_str(string)


def load(override_cfg_file: str | None = None):
    conf_parser = _get_config(override_cfg_file)

    configured_sections = {
        clazz.__name__: typing.get_type_hints(clazz).keys()
        for clazz in BaseConfig.__subclasses__()
        if clazz.__name__ in conf_parser
    }
    for section in set(conf_parser.sections()) - configured_sections.keys():
        logger.warning("Unknown section '%s' in config file", section)

    for section, known_settings in configured_sections.items():
        for setting in conf_parser[section].keys() - known_settings:
            logger.warning("Unknown setting '%s' in config file section '%s'", setting, section)

    for clazz in BaseConfig.__subclasses__():
        for prop, conv in typing.get_type_hints(clazz).items():
            try:
                str_val = conf_parser.get(clazz.__name__, prop, raw=True)
            except configparser.Error:
                continue

            try:
                val = _convert(conv, str_val)
                setattr(clazz, prop, val)
            except ValueError as err:
                message = f"Value '{str_val}' for {clazz.__name__}.{prop} is invalid"
                raise BadConfigError(message) from err


def dumps() -> str:
    conf_parser = configparser.ConfigParser(interpolation=None)
    strio = io.StringIO()

    def _serialize(val):
        if isinstance(val, Enum):
            return val.value
        if isinstance(val, list):
            return ", ".join(map(_serialize, val))
        if isinstance(val, bool):
            return str(val).lower()
        if isinstance(val, tuple):
            return ":".join(map(_serialize, val))

        return val

    for clazz in BaseConfig.__subclasses__():
        conf_parser[clazz.__name__] = {
            k: _serialize(v) for k, v in clazz.__dict__.items() if not k.startswith("_")
        }

    conf_parser.write(strio)
    return strio.getvalue()


def dump(txt_io: TextIO) -> None:
    txt_io.write(dumps())
