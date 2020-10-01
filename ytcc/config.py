# ytcc - The YouTube channel checker
# Copyright (C) 2020  Wolfgang Popp
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
import inspect
import io
import logging
import os
import sys
import typing
from enum import Enum, EnumMeta
from pathlib import Path
from typing import Optional, TextIO, Type, Any, List, Callable, Tuple, Sequence

from ytcc.exceptions import BadConfigException

logger = logging.getLogger(__name__)

_BOOLEAN_STATES = {'1': True, 'yes': True, 'true': True, 'on': True,
                   '0': False, 'no': False, 'false': False, 'off': False}


class Color(int):
    def __new__(cls, val):
        i = super().__new__(cls, val)
        if 0 >= i >= 255:
            raise ValueError(f"{val} is not a valid color. "
                             "Must be in greater than 0 and less than 255")
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
    EXTRACTOR_HASH = "extractor_hash"
    PLAYLISTS = "playlists"

    @staticmethod
    def from_str(string: str) -> "VideoAttr":
        v_attr = VideoAttr.__members__.get(string.upper())  # pylint: disable=no-member
        if v_attr is not None:
            return v_attr
        raise ValueError(f"{string} cannot be converted to VideoAttr")


class PlaylistAttr(str, Enum):
    NAME = "name"
    URL = "url"
    TAGS = "tags"

    @staticmethod
    def from_str(string: str) -> "PlaylistAttr":
        p_attr = PlaylistAttr.__members__.get(string.upper())  # pylint: disable=no-member
        if p_attr is not None:
            return p_attr
        raise ValueError(f"{string} cannot be converted to PlaylistAttr")


class Direction(str, Enum):
    ASC = "asc"
    DESC = "desc"


class DateFormatStr(str):
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


class ytcc(BaseConfig):  # pylint: disable=invalid-name
    download_dir: str = "~/Downloads"
    mpv_flags: str = "--really-quiet --ytdl --ytdl-format=bestvideo[height<=?1080]+bestaudio/best"
    order_by: List[Tuple[VideoAttr, Direction]] = [
        (VideoAttr.PLAYLISTS, Direction.ASC),
        (VideoAttr.PUBLISH_DATE, Direction.DESC),
    ]
    video_attrs: List[VideoAttr] = [
        VideoAttr.ID,
        VideoAttr.TITLE,
        VideoAttr.PUBLISH_DATE,
        VideoAttr.DURATION,
        VideoAttr.PLAYLISTS
    ]
    playlist_attrs: List[PlaylistAttr] = list(PlaylistAttr)
    db_path: str = "~/.local/share/ytcc/ytcc.db"
    date_format: DateFormatStr = DateFormatStr("%Y-%m-%d")
    max_update_fail: int = 5
    max_update_backlog: int = 20
    age_limit: int = 0


class tui(BaseConfig):  # pylint: disable=invalid-name
    alphabet: str = "sdfervghnuiojkl"
    default_action: Action = Action.PLAY_VIDEO


class theme(BaseConfig):  # pylint: disable=invalid-name
    prompt_download_audio: Color = Color(2)
    prompt_download_video: Color = Color(4)
    prompt_play_audio: Color = Color(2)
    prompt_play_video: Color = Color(4)
    prompt_mark_watched: Color = Color(1)
    table_alternate_background: Color = Color(245)


class youtube_dl(BaseConfig):  # pylint: disable=invalid-name
    format: str = "bestvideo[height<=?1080]+bestaudio/best"
    output_template: str = "%(title)s.%(ext)s"
    ratelimit: int = 0
    retries: int = 0
    subtitles: List[str] = ["off"]
    thumbnail: bool = True
    skip_live_stream: bool = True
    merge_output_format: str = "mkv"


def _get_config(override_cfg_file: Optional[str] = None) -> configparser.ConfigParser:
    """Read config file from several locations.

    Searches at following locations:
    1. ``override_cfg_file``
    2. ``$XDG_CONFIG_HOME/ytcc/ytcc.conf``
    3. ``~/.config/ytcc/ytcc.conf``
    4. ``~/.ytcc.conf``

    If no config file is found in these three locations, a default config file is created in
    ``~/.config/ytcc/ytcc.conf``

    :param override_cfg_file: Read the config from this file.
    :return: The dict-like config object
    """
    config_dir = os.getenv("XDG_CONFIG_HOME")
    if not config_dir:
        config_dir = "~/.config"

    global_cfg_file = "/etc/ytcc/ytcc.conf"
    default_cfg_file = os.path.expanduser(config_dir + "/ytcc/ytcc.conf")
    fallback_cfg_file = os.path.expanduser("~/.ytcc.conf")

    config = configparser.ConfigParser(interpolation=None)

    cfg_file_locations = [global_cfg_file, default_cfg_file, fallback_cfg_file]
    if override_cfg_file:
        cfg_file_locations.append(override_cfg_file)

    logger.debug("Reading config from following locations: %s", cfg_file_locations)

    if not config.read(cfg_file_locations):
        logger.debug("No config file found. Creating new config at %s", default_cfg_file)
        path = Path(default_cfg_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        with path.open("w") as conf_file:
            dump(conf_file)

    return config


def _is_config_class(member) -> bool:
    return inspect.isclass(member) and member is not BaseConfig and issubclass(member, BaseConfig)


_config_classes = inspect.getmembers(sys.modules[__name__], _is_config_class)


def load(override_cfg_file: Optional[str] = None):
    conf_parser = _get_config(override_cfg_file)

    def enum_from_str(e_class: EnumMeta, str_val: str) -> Enum:
        field: Any
        for field in e_class:
            # Might also raise a ValueError
            converted_val = _convert(field.value.__class__, str_val)
            if field.value == converted_val:
                return field

        raise ValueError(f"{str_val} is not a valid {e_class}")

    def bool_from_str(string: str) -> bool:
        bool_state = _BOOLEAN_STATES.get(string.lower())
        if bool_state is None:
            raise ValueError(f"{string} cannot be converted to bool")
        return bool_state

    def list_from_str(elem_type: Type, list_str: str) -> List[Any]:
        return [_convert(elem_type, elem.strip()) for elem in list_str.split(",")]

    def tuple_from_str(types: Sequence[Type], tuple_str) -> Tuple:
        elems = tuple_str.split(":")
        if len(elems) != len(types):
            raise ValueError(f"{tuple_str} cannot be converted to tuple of type {types}")

        return tuple(_convert(typ, elem) for elem, typ in zip(elems, types))

    def _convert(typ: Type[Any], string: str) -> Any:
        if typing.get_origin(typ) is list:
            elem_conv = typing.get_args(typ)[0]
            from_str: Callable[[str], Any] = functools.partial(list_from_str, elem_conv)
        elif typing.get_origin(typ) is tuple:
            from_str = functools.partial(tuple_from_str, typing.get_args(typ))
        elif isinstance(typ, EnumMeta):
            from_str = functools.partial(enum_from_str, typ)
        elif issubclass(typ, bool):
            from_str = bool_from_str
        elif next((c for c in {int, float, str} if issubclass(typ, c)), None):
            from_str = typ
        else:
            raise TypeError(f"Unsupported config parameter type in {typ}")

        return from_str(string)

    for class_name, config_class in _config_classes:
        for prop, conv in typing.get_type_hints(config_class).items():

            try:
                str_val = conf_parser.get(class_name, prop, raw=True)
            except configparser.Error:
                continue

            try:
                val = _convert(conv, str_val)
                setattr(config_class, prop, val)
            except ValueError as err:
                message = f"Value '{str_val}' for {class_name}.{prop} is invalid"
                raise BadConfigException(message) from err


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

    for name, clazz in _config_classes:
        conf_parser[name] = {
            k: _serialize(v)
            for k, v in clazz.__dict__.items()
            if not k.startswith("__")
        }

    conf_parser.write(strio)
    return strio.getvalue()


def dump(txt_io: TextIO) -> None:
    txt_io.write(dumps())
