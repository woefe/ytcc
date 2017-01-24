# ytcc - The YouTube channel checker
# Copyright (C) 2017  Wolfgang Popp
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

from pathlib import Path
import configparser
import os
import re

DEFAULTS = {
    "YTCC": {
        "DBPath": "~/.local/share/ytcc/ytcc.db",
        "DownloadDir": "~/Downloads",
        "mpvFlags": "--really-quiet --ytdl --ytdl-format=bestvideo[height<=?1080]+bestaudio/best",
        "ytdlOutputTemplate": "%(title)s.%(ext)s"
    },
    "TableFormat": {
        "ID": "on",
        "Date": "off",
        "Channel": "on",
        "Title": "on",
        "URL": "off"
    }
}

def _get_config():
    """Searches for the config file in
        1. $XDG_CONFIG_HOME/ytcc/ytcc.conf
        2. ~/.config/ytcc/ytcc.conf
        3. ~/.ytcc.conf
    If no config file is found in these three locations, a default config file is created in
    '~/.config/ytcc/ytcc.conf'

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

    if len(config.read([global_cfg_file, default_cfg_file, fallback_cfg_file])) < 1:
        path = Path(default_cfg_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        with path.open("w") as conf_file:
            config.write(conf_file)

    return config


class Config(object):
    """Handles the ini-based configuration file"""

    def __init__(self):
        super(Config, self).__init__()
        config = _get_config()
        self.download_dir = os.path.expanduser(config["YTCC"]["DownloadDir"])
        self.db_path = os.path.expanduser(config["YTCC"]["DBPath"])
        self.mpv_flags = re.compile("\\s+").split(config["YTCC"]["mpvFlags"])
        self.ytdl_output_template = config["YTCC"]["ytdlOutputTemplate"]
        self.table_format = config["TableFormat"]
