# ytcc - The YouTube channel checker
# Copyright (C) 2016  Wolfgang Popp
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
from urllib.parse import urlparse
from lxml import etree
from io import StringIO
from itertools import chain
from pathlib import Path
from multiprocessing import Pool
from ytcc import database
import configparser
import feedparser
import sqlite3
import time
import re
import subprocess
import os
import youtube_dl


class YtccException(Exception):
    """A general parent class of all Exceptions that are used in Ytcc"""

    def __init__(self, message):
        self.message = message


class DownloadError(YtccException):
    """Raised when the download via youtube-dl fails"""

    def __init__(self, message):
        self.message = message


class BadURLException(YtccException):
    """Raised when a given URL does not refer to a YouTube channel."""

    def __init__(self, message):
        self.message = message


class DuplicateChannelException(YtccException):
    """Raised when trying to subscribe to a channel the second (or more) time."""

    def __init__(self, message):
        self.message = message


class ChannelDoesNotExistException(YtccException):
    """Raised when the url of a given channel does not exist."""

    def __init__(self, message):
        self.message = message


class InvalidIDException(YtccException):
    """Raised when a given video ID or channel ID does not exist."""

    def __init__(self, message):
        self.message = message


class InvalidSubscriptionFile(YtccException):
    """Raised when the given file is not a valid XML file."""

    def __init__(self, message):
        self.message = message

class Ytcc:
    """The Ytcc class handles updating the YouTube RSS feed and playing and listing/filtering videos. Filters can be set
    with with following methods:
        set_channel_filter
        set_date_begin_filter
        set_date_end_filter
        set_include_watched_filter
    """

    def __init__(self):
        self.config = self._get_config()
        self.download_dir = os.path.expanduser(self.config["YTCC"]["DownloadDir"])
        self.dbPath = os.path.expanduser(self.config["YTCC"]["DBPath"])
        self.mpv_flags = re.compile("\\s+").split(self.config["YTCC"]["mpvFlags"])
        self.db = database.Database(Path(self.dbPath))
        self.channel_filter = None
        self.date_begin_filter = 0
        self.date_end_filter = time.mktime(time.gmtime()) + 20
        self.include_watched_filter = False
        self.search_filter = None

    @staticmethod
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

        defaults = {"YTCC": {"DBPath": "~/.local/share/ytcc/ytcc.db",
                             "DownloadDir": "~/Downloads",
                             "mpvFlags": "--really-quiet --ytdl --ytdl-format=bestvideo[height<=?1080]+bestaudio/best"},
                    "TableFormat": {"ID": "on",
                                    "Date": "off",
                                    "Channel": "on",
                                    "Title": "on",
                                    "URL": "off"}
                    }
        config = configparser.ConfigParser()
        config.read_dict(defaults)
        config_file = None
        default = Path(os.path.expanduser("~/.config/ytcc/ytcc.conf"))
        fallback = Path(os.path.expanduser("~/.ytcc.conf"))
        xdg_conf_home = os.getenv("XDG_CONFIG_HOME")
        xdg_conf_file = None

        if xdg_conf_home is not None:
            xdg_conf_file = Path(xdg_conf_home + "/ytcc/ytcc.conf")

        if xdg_conf_file is not None and xdg_conf_file.is_file():
            config_file = str(xdg_conf_file)
        elif default.is_file():
            config_file = str(default)
        elif fallback.is_file():
            config_file = str(fallback)

        if config_file is None:
            config_file = str(default)
            default.parent.mkdir(parents=True, exist_ok=True)
            default.touch()
            with default.open("w") as defaultFile:
                config.write(defaultFile)

        config.read(config_file)
        return config

    @staticmethod
    def get_youtube_video_url(yt_videoid):
        return "https://www.youtube.com/watch?v=" + yt_videoid

    def set_channel_filter(self, channel_filter):
        """Sets the channel filter. The results when listing videos will only include videos by channels specifide in
        the filter

        Args:
            channel_filter (list): the list of channel names
        """

        self.channel_filter = channel_filter

    def set_date_begin_filter(self, begin):
        """Sets the time filter. The results when listing videos will only include videos newer than the given time.

        Args:
            begin (datetime.datetime): the lower bound of the time filter
        """

        self.date_begin_filter = begin.timestamp()

    def set_date_end_filter(self, end):
        """Sets the time filter. The results when listing videos will only include videos older than the given time.

        Args:
            end (datetime.datetime): the upper bound of the time filter
        """

        self.date_end_filter = end.timestamp()

    def set_include_watched_filter(self):
        """Sets "watched video" filter. The results when listing videos will include both watched and unwatched videos.
        """

        self.include_watched_filter = True

    def set_search_filter(self, searchterm):
        """Sets a search filter. When this filter is set, all other filters are ignored

        Args:
            searchterm (str): only videos whose title, channel or description match this term will be included
        """

        self.search_filter = searchterm

    @staticmethod
    def _update_channel(yt_channel_id):
        feed = feedparser.parse("https://www.youtube.com/feeds/videos.xml?channel_id=" + yt_channel_id)
        return [(entry.yt_videoid,
                   entry.title,
                   entry.description,
                   yt_channel_id,
                   time.mktime(entry.published_parsed),
                   0)
                  for entry in feed.entries]

    def update_all(self):
        """Checks every channel for new videos"""

        channels = map(lambda channel: channel.yt_channelid, self.db.list_channels())

        with Pool(os.cpu_count() * 2) as pool:
            videos = chain.from_iterable(pool.map(self._update_channel, channels))

        with database.Database(Path(self.dbPath)) as db:
            db.add_videos(videos)

    def play_video(self, video_id, no_video=False):
        """Plays the video identified by the given video ID with the mpv video player and marks the video watched, if
        the player exits with an exit code of zero.

        Args:
            video_id (int): The (local) video ID.
            no_video (bool): If True only the audio is played

        Returns (bool):
            False if the given video_id does not exist or the player closed with a non zero exit code. True if the video
            was played successfully.
        """

        no_video_flag = []
        if no_video:
            no_video_flag.append("--no-video")

        video = self.db.get_video(video_id)
        if video:
            mpv_result = subprocess.run(["mpv", *no_video_flag, *self.mpv_flags,
                                         self.get_youtube_video_url(video.yt_videoid)],
                                        stderr=subprocess.DEVNULL)
            if mpv_result.returncode == 0:
                self.db.mark_some_watched([video.id])
                return True

        return False

    def download_videos(self, video_ids=None, path=None, no_video=False):
        """Downloads the videos identified by the given video IDs with youtube-dl and marks the videos watched.

        Args:
            video_ids ([int]): The (local) video IDs.
            path (str): The directory where the download is saved.
            no_video (bool): If True only the audio is downloaded
        """

        if path:
            download_dir = path
        elif self.download_dir:
            download_dir = self.download_dir
        else:
            download_dir = os.path.expanduser("~/Downloads")

        if not os.path.isdir(download_dir):
            raise DownloadError(download_dir + " is not a directory")

        no_video_flag = []
        if no_video:
            no_video_flag.append("--extract-audio")

        if not video_ids:
            video_ids = self._get_filtered_video_ids()

        videos = self.get_videos(video_ids)
        urls = list(map(lambda v: self.get_youtube_video_url(v.yt_videoid), videos))

        ydl_opts = {
            "outtmpl": download_dir + "/%(title)s.%(ext)s",
        }

        if no_video:
            ydl_opts["format"] = "bestaudio/best"

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            if ydl.download(urls) == 0:
                self.db.mark_some_watched(video_ids)
            else:
                raise DownloadError("youtube-dl return with an error")

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

    def import_channels(self, file):
        try:
            root = etree.parse(file)
        except Exception:
            raise InvalidSubscriptionFile("'" + file.name + "' is not a valid YouTube export file")

        elements = root.xpath('//outline[@type="rss"]')
        channels = [(e.attrib["title"], urlparse(e.attrib["xmlUrl"]).query[11:]) for e in elements]

        for channel in channels:
            try:
                self.db.add_channel(*channel)
            except sqlite3.IntegrityError:
                pass

    def list_videos(self):
        """Returns a list of videos that match the filters set by the set_*_filter methods.

        Returns (list):
            A list of ytcc.video.Video objects
        """

        if self.search_filter:
            return self.db.search(self.search_filter)

        return self.db.list_videos(self.channel_filter, self.date_begin_filter, self.date_end_filter,
                                   self.include_watched_filter)

    def _get_filtered_video_ids(self):
        return list(map(lambda video: video.id, self.list_videos()))

    def mark_watched(self, video_ids=None):
        """Marks the videos of channels specified in the filter as watched without playing them. The filters are set by
        the set_*_filter methods.

        Args:
            video_ids ([int]): The video IDs to mark as watched.

        Returns (list):
            A list of ytcc.video.Video objects. Contains the videos that were marked watched.
        """

        if video_ids:
            mark_ids = video_ids
        else:
            mark_ids = self._get_filtered_video_ids()

        self.db.mark_some_watched(mark_ids)
        return self.get_videos(mark_ids)

    def delete_channels(self, displaynames):
        """Delete (or unsubscribe) channels.

        Args:
            displaynames (list): A list of channels' displaynames.
        """

        self.db.delete_channels(displaynames)

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
