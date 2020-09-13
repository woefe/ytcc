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
import os
import sys
from enum import Enum, EnumMeta
from pathlib import Path
from typing import Optional, TextIO, Type, Any, List

import typing

from ytcc.exceptions import BadConfigException

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
    play_video = "play_video"
    play_audio = "play_audio"
    mark_watched = "mark_watched"
    download_audio = "download_audio"
    download_video = "download_video"


class LogLevel(str, Enum):
    normal = "normal"
    quiet = "quiet"
    verbose = "verbose"


class VideoAttr(str, Enum):
    id = "id"
    url = "url"
    title = "title"
    description = "description"
    publish_date = "publish_date"
    watched = "watched"
    duration = "duration"
    extractor_hash = "extractor_hash"
    playlists = "playlists"


class PlaylistAttr(str, Enum):
    name = "name"
    url = "url"
    tags = "tags"


class BaseConfig:
    def __setattr__(self, key, value):
        raise AttributeError("Attribute is immutable")


class ytcc(BaseConfig):
    download_dir: str = "~/Downloads"
    mpv_flags: str = "--really-quiet --ytdl --ytdl-format=bestvideo[height<=?1080]+bestaudio/best"
    order_by: List[VideoAttr] = [VideoAttr.playlists, VideoAttr.publish_date]
    video_attrs: List[VideoAttr] = [
        VideoAttr.id,
        VideoAttr.title,
        VideoAttr.publish_date,
        VideoAttr.duration,
        VideoAttr.playlists
    ]
    playlist_attrs: List[PlaylistAttr] = list(PlaylistAttr)
    db_path: str = "~/.local/share/ytcc/ytcc.db"
    loglevel: LogLevel = "normal"


class tui(BaseConfig):
    alphabet: str = "sdfervghnuiojkl"
    default_action: Action = Action.play_video


class theme(BaseConfig):
    prompt_download_audio: Color = 2
    prompt_download_video: Color = 4
    prompt_play_audio: Color = 2
    prompt_play_video: Color = 4
    prompt_mark_watched: Color = 1
    table_alternate_background: Color = 245


class youtube_dl(BaseConfig):
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

    if not config.read(cfg_file_locations):
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
    cp = _get_config(override_cfg_file)

    def enum_from_str(e_class: EnumMeta, str_val: str) -> Enum:
        for e in e_class:
            converted_val = _convert(e.value.__class__, str_val)  # Might also raise a ValueError
            if e.value == converted_val:
                return e

        raise ValueError(f"{str_val} is not a valid {e_class}")

    def bool_from_str(s: str) -> bool:
        b = _BOOLEAN_STATES.get(s.lower())
        if b is None:
            ValueError(f"{s} cannot be converted to bool")
        return b

    def list_from_str(elem_type: Type, list_str: str) -> List[Any]:
        return [_convert(elem_type, elem.strip()) for elem in list_str.split(",")]

    def _convert(typ: Type, string: str):
        if typing.get_origin(typ) is list:
            elem_conv = typing.get_args(typ)[0]
            from_str = functools.partial(list_from_str, elem_conv)
        elif issubclass(typ, Enum):
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
                str_val = cp.get(class_name, prop, raw=True)
            except configparser.Error:
                continue

            try:
                val = _convert(conv, str_val)
                setattr(config_class, prop, val)
            except ValueError:
                raise BadConfigException(f"Value {str_val} for {class_name}.{prop} is invalid")


def dumps() -> str:
    cp = configparser.ConfigParser(interpolation=None)
    strio = io.StringIO()

    def _serialize(v):
        if isinstance(v, Enum):
            return v.value
        if isinstance(v, list):
            return ", ".join(map(_serialize, v))
        if isinstance(v, bool):
            return str(v).lower()

        return v

    for name, clazz in _config_classes:
        cp[name] = {k: _serialize(v) for k, v in clazz.__dict__.items() if not k.startswith("__")}

    cp.write(strio)
    return strio.getvalue()


def dump(fd: TextIO) -> None:
    fd.write(dumps())


load()
