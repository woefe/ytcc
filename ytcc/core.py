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
    """Raised when a given video id or channel id does not exist."""

    def __init__(self, message):
        self.message = message

class Ytcc:

    def __init__(self):
        self.dbPath = Path(self._get_db_path())
        self.db = database.Database(self.dbPath)

    def _get_db_path(self):
        confFile = self._get_conf_file()
        config = configparser.ConfigParser()
        config.read(str(confFile))
        return config['YTCC']["DBPath"]


    def _get_conf_file(self):
        xdgConfHome = os.getenv("XDG_CONFIG_HOME")
        if xdgConfHome is not None:
            confFile = Path(xdgConfHome + "/ytcc/ytcc.conf")
            if confFile.is_file():
                return confFile

        default = Path(os.path.expanduser("~/.config/ytcc/ytcc.conf"))
        if default.is_file():
            return default

        confFile = Path(os.path.expanduser("~/.ytcc.conf"))
        if confFile.is_file():
            return confFile

        # Create config if it does not exist.
        config = configparser.ConfigParser()
        config['YTCC'] = {"dbpath" : "~/.local/share/ytcc/ytcc.db"}
        default.parent.mkdir(parents=True, exist_ok=True)
        default.touch()
        with default.open("w") as defaultFile:
            config.write(defaultFile)

        return Path(default)


    def _update_channel(self, ytChannelId, isInitialUpdate=False):
        feed = feedparser.parse("https://www.youtube.com/feeds/videos.xml?channel_id=" + ytChannelId)
        videos = [(entry.yt_videoid,
                    entry.title,
                    entry.description,
                    ytChannelId,
                    time.mktime(entry.published_parsed),
                    0)
                    for entry in feed.entries]

        with database.Database(self.dbPath) as db:
            db.add_videos(videos)

    def update_all(self):
        """Checks every channel for new videos"""

        with Pool(os.cpu_count() * 2) as threadPool:
            threadPool.map(self._update_channel, self.db.list_channel_yt_ids())

    def play_video(self, vID):
        """Plays the video identified by vID with the mpv video player and marks
        the video watched.

        Args:
            vID (int): The (local) video id.
        """

        ytVideoId = self.db.get_yt_video_id(vID)
        if ytVideoId:
            os.system("mpv --really-quiet https://www.youtube.com/watch?v=" + ytVideoId + " 2> /dev/null")
            self.db.video_watched(vID)

    def download_video(self, vID, path):
        """Downloads the video identified by vID with youtube-dl and marks the
        video watched.

        Args:
            vID (int): The (local) video id.
            path (str): The directory where the download is saved.
        """

        ytVideoId = self.db.get_yt_video_id(vID)
        if os.path.isdir(path) and ytVideoId:
            os.system("youtube-dl -o '" + path + "/%(title)s' https://www.youtube.com/watch?v=" + ytVideoId)
            self.db.video_watched(vID)

    def add_channel(self, diplayname, channelURL):
        """Subscribes to a channel.

        Args:
            displayname (str): a human readable name of the channel.
            channelURL (str): the url to the channel's home page.

        Raises:
            ChannelDoesNotExistException: when the given URL does not exist.
            DuplicateChannelException: when trying to subscribe to a channel the
                second (or more) time.
            BadURLException: when a given URL does not refer to a YouTube
                channel.
        """

        regex = "^(https?://)?(www\.)?youtube\.com/(?P<type>user|channel)/(?P<channel>[^/?=]+)$"
        match = re.search(regex, channelURL)

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
                self.db.add_channel(diplayname, yt_channelid)
            except sqlite3.IntegrityError:
                raise DuplicateChannelException("Channel already subscribed: " + channel)

        else:
            raise BadURLException("'" + channelURL + "' is not a valid URL")

    def list_unwatched_videos(self, channelFilter=None):
        """Returns a list of unwatched videos.

        Returns (list):
            A list of tuples of the form (vID, title, description, publish_date, channel).
        """

        if channelFilter:
            return self.db.list_unwatched_videos_with_filter(channelFilter)
        else:
            return self.db.list_unwatched_videos()

    def mark_some_watched(self, vIDs):
        """Marks the videos identified by vIDs as watched without playing them.
        Invalid video ids are ignored.

        Args:
            vIDs (list of int): The video IDs to mark as watched.
        """

        self.db.mark_some_watched(vIDs)

    def mark_watched(self, channelFilter=None):
        """Marks the videos of channels specified in the filter as watched
        witout playing them. If channelFilter is None all unwatched videos are
        marked as watched.

        Args:
            channelFilter ([int]): the channel filter.
        """

        if channelFilter:
            self.db.mark_watched(channelFilter)
        else:
            self.db.mark_all_watched()

    def list_recent_videos(self, channelFilter=None):
        """Returns a list of videos that were added within the last week.

        Returns (list):
            A list of tuples of the form (vID, title, description, publish_date, channel)
        """

        if channelFilter:
            return self.db.list_recent_videos_with_filter(channelFilter)
        else:
            return self.db.list_recent_videos()

    def delete_channel(self, channelID):
        """Delete (or unsubscribe) a channel.

        Args:
            cID (int): The channel's ID.
        """

        self.db.delete_channel(channelID)

    def list_channels(self):
        """Returns a list of all subscribed channels.

        Returns ([(int, str)]):
            A list of tuples of the form (id, name).
        """

        return self.db.list_channels()

    def get_video_info(self, vID):
        """Returns id, title, description, publish date, channel name for a
        given video id.

        Returns (tuple)
            The tuple containing all the above listed information or None if the
            id does not exist.
        """

        return self.db.get_video_info(vID)
