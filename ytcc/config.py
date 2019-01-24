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

import configparser
import io
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULTS: Dict[str, Dict[str, Any]] = {
    "YTCC": {
        "DBPath": "~/.local/share/ytcc/ytcc.db",
        "DownloadDir": "~/Downloads",
        "mpvFlags": "--really-quiet --ytdl --ytdl-format=bestvideo[height<=?1080]+bestaudio/best",
        "orderBy": "channel_id,publish_date"
    },
    "youtube-dl": {
        "format": "bestvideo[height<=?1080]+bestaudio/best",
        "outputTemplate": "%(title)s.%(ext)s",
        "loglevel": "normal",
        "ratelimit": 0,
        "retries": 0,
        "subtitles": "off",
        "thumbnail": "on",
        "skipLiveStream": "yes"
    },
    "quickselect": {
        "enabled": "yes",
        "ask": "yes",
        "alphabet": "sdfervghnuiojkl"
    },
    "TableFormat": {
        "ID": "on",
        "Date": "off",
        "Channel": "on",
        "Title": "on",
        "URL": "off",
        "Watched": "off"
    }
}


def _get_config(override_cfg_file: Optional[str] = None) -> configparser.ConfigParser:
    """Searches for the config file in
        0. override_cfg_file
        1. $XDG_CONFIG_HOME/ytcc/ytcc.conf
        2. ~/.config/ytcc/ytcc.conf
        3. ~/.ytcc.conf
    If no config file is found in these three locations, a default config file is created in
    '~/.config/ytcc/ytcc.conf'

    Args:
        override_cfg_file (str): reads the config from the given file

    Returns (configparser.ConfigParser):
        the config
    """

    config_dir = os.getenv("XDG_CONFIG_HOME")
    if not config_dir:
        config_dir = "~/.config"

    global_cfg_file = "/etc/ytcc/ytcc.conf"
    default_cfg_file = os.path.expanduser(config_dir + "/ytcc/ytcc.conf")
    fallback_cfg_file = os.path.expanduser("~/.ytcc.conf")

    config = configparser.ConfigParser(interpolation=None)
    config.read_dict(DEFAULTS)

    cfg_file_locations = [global_cfg_file, default_cfg_file, fallback_cfg_file]
    if override_cfg_file:
        cfg_file_locations.append(override_cfg_file)

    if len(config.read(cfg_file_locations)) < 1:
        path = Path(default_cfg_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        with path.open("w") as conf_file:
            config.write(conf_file)

    return config


class Config(object):
    """Handles the ini-based configuration file"""

    def __init__(self, override_cfg_file: Optional[str] = None) -> None:
        super(Config, self).__init__()
        config = _get_config(override_cfg_file)
        self._config = config
        self.download_dir = os.path.expanduser(config["YTCC"]["DownloadDir"])
        self.db_path = os.path.expanduser(config["YTCC"]["DBPath"])
        self.mpv_flags = re.compile("\\s+").split(config["YTCC"]["mpvFlags"])
        self.orderby = config["YTCC"]["orderBy"].split(",")
        self.table_format = config["TableFormat"]
        self.youtube_dl = _YTDLConf(config["youtube-dl"])
        self.quickselect = _QuickSelectConf(config["quickselect"])

    def __str__(self) -> str:
        strio = io.StringIO()
        self._config.write(strio)
        return strio.getvalue()


class _QuickSelectConf(object):
    def __init__(self, subconf: Any) -> None:
        super(_QuickSelectConf, self).__init__()
        self.enabled = subconf.getboolean("enabled")
        self.ask = subconf.getboolean("ask")
        self.alphabet = subconf["alphabet"]


class _YTDLConf(object):
    def __init__(self, subconf: Any) -> None:
        super(_YTDLConf, self).__init__()
        self.format = subconf["format"]
        self.output_template = subconf["outputTemplate"]
        self.loglevel = subconf["loglevel"]
        self.retries = float(subconf["retries"])  # float to set indefinetly many retires
        self.subtitles = subconf["subtitles"]
        self.thumbnail = subconf.getboolean("thumbnail")
        self.skip_live_stream = subconf.getboolean("skipLiveStream")

        limit = int(subconf["ratelimit"])
        self.ratelimit = limit if limit > 0 else None
