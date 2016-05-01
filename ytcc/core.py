# ytcc - The YouTube channel checker
# Copyright (C) 2015  Wolfgang Popp
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

from urllib.request import urlopen
from urllib.error import URLError
from lxml import etree
from io import StringIO
from pathlib import Path
from multiprocessing import Pool
from ytcc import database
import configparser
import feedparser
import sqlite3
import time
import re
import os


class BadURLException(Exception):
    """Raised when a given URL does not refer to a YouTube channel."""

    def __init__(self, message):
        self.message = message


class DuplicateChannelException(Exception):
    """Raised when trying to subscribe to a channel the second (or more) time."""

    def __init__(self, message):
        self.message = message


class ChannelDoesNotExistException(Exception):
    """Raised when the url of a given channel does not exist."""

    def __init__(self, message):
        self.message = message


class InvalidIDException(Exception):
    """Raised when a given video ID or channel ID does not exist."""

    def __init__(self, message):
        self.message = message


class Ytcc:
    DEFAULT_DB_PATH = "~/.local/share/ytcc/ytcc.db"
    DEFAULT_DLOAD_DIR = "~/Downloads"

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read(str(self._get_conf_file()))

        self.download_dir = os.path.expanduser(self.config["YTCC"]["DownloadDir"])
        self.dbPath = os.path.expanduser(self.config["YTCC"]["DBPath"])
        self.db = database.Database(Path(self.dbPath))


    @staticmethod
    def _get_conf_file():
        """Searches for the config file in
            1. $XDG_CONFIG_HOME/ytcc/ytcc.conf
            2. ~/.config/ytcc/ytcc.conf
            3. ~/.ytcc.conf
        If no config file is found in these three locations, a default config file is created in
        '~/.config/ytcc/ytcc.conf'
        """

        xdg_conf_home = os.getenv("XDG_CONFIG_HOME")
        if xdg_conf_home is not None:
            conf_file = Path(xdg_conf_home + "/ytcc/ytcc.conf")
            if conf_file.is_file():
                return conf_file

        default = Path(os.path.expanduser("~/.config/ytcc/ytcc.conf"))
        if default.is_file():
            return default

        conf_file = Path(os.path.expanduser("~/.ytcc.conf"))
        if conf_file.is_file():
            return conf_file

        # Create config if it does not exist.
        config = configparser.ConfigParser()
        config["YTCC"] = {
                "DBPath": DEFAULT_DB_PATH,
                "DownloadDir": DEFAULT_DLOAD_DIR
                }
        default.parent.mkdir(parents=True, exist_ok=True)
        default.touch()
        with default.open("w") as defaultFile:
            config.write(defaultFile)

        return Path(default)

    def _update_channel(self, yt_channel_id):
        feed = feedparser.parse("https://www.youtube.com/feeds/videos.xml?channel_id=" + yt_channel_id)
        videos = [(entry.yt_videoid,
                   entry.title,
                   entry.description,
                   yt_channel_id,
                   time.mktime(entry.published_parsed),
                   0)
                  for entry in feed.entries]

        with database.Database(Path(self.dbPath)) as db:
            db.add_videos(videos)

    def update_all(self):
        """Checks every channel for new videos"""

        with Pool(os.cpu_count() * 2) as threadPool:
            threadPool.map(self._update_channel, map(lambda channel: channel.yt_channelid, self.db.list_channels()))

    def play_video(self, video_id):
        """Plays the video identified by the given video ID with the mpv video player and marks the video watched.

        Args:
            video_id (int): The (local) video ID.
        """

        video = self.db.get_video(video_id)
        if video:
            os.system("mpv --really-quiet https://www.youtube.com/watch?v=" + video.yt_videoid + " 2> /dev/null")
            self.db.mark_some_watched([video.id])

    def download_videos(self, video_ids, path):
        """Downloads the videos identified by the given video IDs with youtube-dl and marks the videos watched.

        Args:
            video_ids ([int]): The (local) video IDs.
            path (str): The directory where the download is saved.
        """

        download_dir = os.path.expanduser("~/Downloads")

        if self.download_dir:
            download_dir = self.download_dir
        elif path:
            download_dir = path

        if not os.path.isdir(download_dir):
            return

        for vID in video_ids:
            video = self.db.get_video(vID)
            if video:
                os.system("youtube-dl -o '" + download_dir +
                          "/%(title)s' https://www.youtube.com/watch?v=" + video.yt_videoid)
                self.db.mark_some_watched([vID])

    def add_channel(self, displayname, channel_url):
        """Subscribes to a channel.

        Args:
            displayname (str): a human readable name of the channel.
            channel_url (str): the url to the channel's home page.

        Raises:
            ChannelDoesNotExistException: when the given URL does not exist.
            DuplicateChannelException: when trying to subscribe to a channel the second (or more) time.
            BadURLException: when a given URL does not refer to a YouTube channel.
        """

        regex = "^(https?://)?(www\.)?youtube\.com/(?P<type>user|channel)/(?P<channel>[^/?=]+)$"
        match = re.search(regex, channel_url)

        if match:
            channel = match.group("channel")
            url = "https://www.youtube.com/" + match.group("type") + "/" + channel + "/videos"

            try:
                response = urlopen(url).read().decode('utf-8')
            except URLError:
                raise ChannelDoesNotExistException("Channel does not exist: " + channel)

            parser = etree.HTMLParser()
            root = etree.parse(StringIO(response), parser).getroot()
            yt_channelid = root.xpath('/html/head/meta[@itemprop="channelId"]')[0].attrib.get("content")

            try:
                self.db.add_channel(displayname, yt_channelid)
            except sqlite3.IntegrityError:
                raise DuplicateChannelException("Channel already subscribed: " + channel)

        else:
            raise BadURLException("'" + channel_url + "' is not a valid URL")

    def list_unwatched_videos(self, channel_filter=None):
        """Returns a list of unwatched videos. The videos are published by the channels given in the channel filter.

        Args:
            channel_filter ([str]): a list of channel names

        Returns (list):
            A list of ytcc.video.Video objects
        """

        return self.db.list_videos(channel_filter, include_watched=False)

    def mark_some_watched(self, video_ids):
        """Marks the videos identified by the given video IDs as watched without playing them. Invalid video IDs are
        ignored.

        Args:
            video_ids ([int]): The video IDs to mark as watched.
        """

        self.db.mark_some_watched(video_ids)

    def mark_watched(self, channel_filter=None):
        """Marks the videos of channels specified in the filter as watched without playing them. If channelFilter is
        None all unwatched videos are marked as watched.

        Args:
            channel_filter ([int]): the channel filter.
        """

        if channel_filter:
            self.db.mark_watched(channel_filter)
        else:
            self.db.mark_all_watched()

    def list_recent_videos(self, channel_filter=None):
        """Returns a list of videos that were added within the last week. The videos are published by the channels given
        in the channel filter.

        Args:
            channel_filter ([str]): a list of channel names

        Returns (list):
            A list of ytcc.video.Video objects
        """

        return self.db.list_videos(channel_filter, time.mktime(time.gmtime()) - 604800)

    def delete_channel(self, displayname):
        """Delete (or unsubscribe) a channel.

        Args:
            displayname (str): The channel's displayname.
        """

        self.db.delete_channel(displayname)

    def list_channels(self):
        """Returns a list of all subscribed channels.

        Returns ([str]):
            A list of channel names.
        """

        return self.db.list_channels()

    def get_videos(self, video_ids):
        """Returns the ytcc.video.Video object for the given video IDs.

        Args:
            video_ids ([int]): the video IDs.

        Returns (list)
            A list of ytcc.video.Video objects
        """

        # filter None values
        return list(filter(lambda x: x, map(self.db.get_video, video_ids)))

    def cleanup(self):
        """Deletes old videos from the database."""

        self.db.cleanup()
