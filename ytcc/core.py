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

import sqlite3
import time
from itertools import chain

import datetime
import feedparser
import os
import subprocess
import youtube_dl
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from lxml import etree
from typing import Iterable, List, TextIO, Optional, Any, Dict, Tuple
from urllib.error import URLError
from urllib.parse import urlparse, urlunparse, parse_qs
from urllib.request import urlopen

from ytcc.channel import Channel
from ytcc.config import Config
from ytcc.database import Database, DBVideo
from ytcc.utils import unpack_optional
from ytcc.video import Video


class YtccException(Exception):
    """A general parent class of all Exceptions that are used in Ytcc"""
    pass


class BadURLException(YtccException):
    """Raised when a given URL does not refer to a YouTube channel."""
    pass


class DuplicateChannelException(YtccException):
    """Raised when trying to subscribe to a channel the second (or more) time."""
    pass


class ChannelDoesNotExistException(YtccException):
    """Raised when the url of a given channel does not exist."""
    pass


class InvalidIDException(YtccException):
    """Raised when a given video ID or channel ID does not exist."""
    pass


class InvalidSubscriptionFileError(YtccException):
    """Raised when the given file is not a valid XML file."""
    pass


class Ytcc:
    """The Ytcc class handles updating the YouTube RSS feed and playing and listing/filtering
    videos. Filters can be set with with following methods:
        set_channel_filter
        set_date_begin_filter
        set_date_end_filter
        set_include_watched_filter
    """

    def __init__(self, override_cfg_file: Optional[str] = None) -> None:
        self.config = Config(override_cfg_file)
        self.db = Database(self.config.db_path)
        self.channel_filter: List[str] = []
        self.date_begin_filter = 0.0
        self.date_end_filter = time.mktime(time.gmtime()) + 20
        self.include_watched_filter = False
        self.search_filter = ""

    def __enter__(self) -> "Ytcc":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        self.db.__exit__(exc_type, exc_val, exc_tb)

    @staticmethod
    def get_youtube_video_url(yt_videoid: str) -> str:
        """Returns the YouTube URL for the given youtube video ID

        Args:
            yt_videoid (str): the YouTube video ID

        Returns (str):
            the YouTube URL for the given youtube video ID
        """

        return f"https://www.youtube.com/watch?v={yt_videoid}"

    def set_channel_filter(self, channel_filter: List[str]) -> None:
        """Sets the channel filter. The results when listing videos will only include videos by
        channels specifide in the filter

        Args:
            channel_filter (list): the list of channel names
        """

        self.channel_filter.clear()
        self.channel_filter.extend(channel_filter)

    def set_date_begin_filter(self, begin: datetime.datetime) -> None:
        """Sets the time filter. The results when listing videos will only include videos newer
        than the given time.

        Args:
            begin (datetime.datetime): the lower bound of the time filter
        """

        self.date_begin_filter = begin.timestamp()

    def set_date_end_filter(self, end: datetime.datetime) -> None:
        """Sets the time filter. The results when listing videos will only include videos older
        than the given time.

        Args:
            end (datetime.datetime): the upper bound of the time filter
        """

        self.date_end_filter = end.timestamp()

    def set_include_watched_filter(self) -> None:
        """Sets "watched video" filter. The results when listing videos will include both watched
        and unwatched videos.
        """

        self.include_watched_filter = True

    def set_search_filter(self, searchterm: str) -> None:
        """Sets a search filter. When this filter is set, all other filters are ignored

        Args:
            searchterm (str): only videos whose title, channel or description match this term will
                be included
        """

        self.search_filter = searchterm

    @staticmethod
    def _update_channel(yt_channel_id: str) -> List[DBVideo]:
        feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={yt_channel_id}")
        return [(str(entry.yt_videoid),
                 str(entry.title),
                 str(entry.description),
                 yt_channel_id,
                 time.mktime(entry.published_parsed),
                 False)
                for entry in feed.entries]

    def update_all(self) -> None:
        """Checks every channel for new videos"""

        channels = map(lambda channel: channel.yt_channelid, self.db.get_channels())
        num_workers = unpack_optional(os.cpu_count(), lambda: 1) * 3

        with ThreadPoolExecutor(num_workers) as pool:
            videos = chain.from_iterable(pool.map(self._update_channel, channels))

        self.db.add_videos(videos)

    def play_video(self, video_id: int, no_video: bool = False) -> bool:
        """Plays the video identified by the given video ID with the mpv video player and marks the
        video watched, if the player exits with an exit code of zero.

        Args:
            video_id (int): The (local) video ID.
            no_video (bool): If True only the audio is played

        Returns (bool):
            False if the given video_id does not exist or the player closed with a non zero exit
            code. True if the video was played successfully.
        """

        no_video_flag = []
        if no_video:
            no_video_flag.append("--no-video")

        video = self.db.resolve_video_id(video_id)
        if video:
            try:
                mpv_result = subprocess.run(["mpv", *no_video_flag, *self.config.mpv_flags,
                                             self.get_youtube_video_url(video.yt_videoid)])
            except FileNotFoundError:
                raise YtccException("Could not locate the mpv video player!")

            if mpv_result.returncode == 0:
                self.db.mark_watched([video.id])
                return True

        return False

    def download_videos(self, video_ids: Optional[List[int]] = None, path: str = "",
                        no_video: bool = False) -> Iterable[Tuple[int, bool]]:
        """Downloads the videos identified by the given video IDs with youtube-dl.

        Args:
            video_ids ([int]): The (local) video IDs.
            path (str): The directory where the download is saved.
            no_video (bool): If True only the audio is downloaded

        Returns:
            Generator of tuples indicating whether the a download was successful.
        """

        if path:
            download_dir = path
        elif self.config.download_dir:
            download_dir = self.config.download_dir
        else:
            download_dir = ""

        videos = self.get_videos(unpack_optional(video_ids, self._get_filtered_video_ids))
        conf = self.config.youtube_dl

        ydl_opts: Dict[str, Any] = {
            "outtmpl": os.path.join(download_dir, conf.output_template),
            "ratelimit": conf.ratelimit,
            "retries": conf.retries,
            "quiet": conf.loglevel == "quiet",
            "verbose": conf.loglevel == "verbose",
            "ignoreerrors": False
        }

        if no_video:
            ydl_opts["format"] = "bestaudio/best"
            if conf.thumbnail:
                ydl_opts["writethumbnail"] = True
                ydl_opts["postprocessors"] = [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': "m4a"
                    },
                    {"key": "EmbedThumbnail"}
                ]
        else:
            ydl_opts["format"] = conf.format
            if conf.subtitles != "off":
                ydl_opts["subtitleslangs"] = list(map(str.strip, conf.subtitles.split(",")))
                ydl_opts["writesubtitles"] = True
                ydl_opts["writeautomaticsub"] = True
                ydl_opts["postprocessors"] = [{"key": "FFmpegEmbedSubtitle"}]

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            for video in videos:
                url = self.get_youtube_video_url(video.yt_videoid)
                try:
                    info = ydl.extract_info(url, download=False, process=False)
                    if info.get("is_live", False) and conf.skip_live_stream:
                        yield video.id, False

                    ydl.process_ie_result(info, download=True)
                    yield video.id, True
                except youtube_dl.utils.YoutubeDLError:
                    yield video.id, False

    def add_channel(self, displayname: str, channel_url: str) -> None:
        """Subscribes to a channel.

        Args:
            displayname (str): a human readable name of the channel.
            channel_url (str): the url to the channel's home page.

        Raises:
            ChannelDoesNotExistException: when the given URL does not exist.
            DuplicateChannelException: when trying to subscribe to a channel the second (or more)
                                       time.
            BadURLException: when a given URL does not refer to a YouTube channel.
        """
        known_yt_domains = ["youtu.be", "youtube.com", "youtubeeducation.com", "youtubekids.com",
                            "youtube-nocookie.com", "yt.be", "ytimg.com"]

        url_parts = urlparse(channel_url, scheme="https")
        if not url_parts.netloc:
            url_parts = urlparse("https://" + channel_url)

        domain = url_parts.netloc.split(":")[0]
        domain = ".".join(domain.split(".")[-2:])

        if domain not in known_yt_domains:
            raise BadURLException(f"{channel_url} is not a valid URL")

        url = urlunparse(("https", url_parts.netloc, url_parts.path, url_parts.params,
                          url_parts.query, url_parts.fragment))

        try:
            response = urlopen(url).read().decode('utf-8')
        except URLError:
            raise BadURLException(f"{channel_url} is not a valid URL")

        parser = etree.HTMLParser()
        root = etree.parse(StringIO(response), parser).getroot()
        site_name_node = root.xpath('/html/head/meta[@property="og:site_name"]')
        channel_id_node = root.xpath('//meta[@itemprop="channelId"]')

        if not site_name_node or site_name_node[0].attrib.get("content", "") != "YouTube":
            raise BadURLException(f"{channel_url} does not seem to be a YouTube URL")

        if not channel_id_node:
            raise ChannelDoesNotExistException(f"{channel_url} does not seem to be a YouTube URL")

        yt_channelid = channel_id_node[0].attrib.get("content")

        try:
            self.db.add_channel(displayname, yt_channelid)
        except sqlite3.IntegrityError:
            raise DuplicateChannelException(f"Channel already subscribed: {displayname}")

    def import_channels(self, file: TextIO) -> None:
        """Imports all channels from YouTube's subsciption export file.

        Args:
            file (TextIOWrapper): the opened file
        """

        def _create_channel_tuple(elem: etree.Element) -> Tuple[str, str]:
            rss_url = urlparse(elem.attrib["xmlUrl"])
            query_dict = parse_qs(rss_url.query, keep_blank_values=False)
            channel_id = query_dict.get("channel_id", [])
            if len(channel_id) != 1:
                raise InvalidSubscriptionFileError(f"'{file.name}' is not a valid YouTube export file")
            return elem.attrib["title"], channel_id[0]

        try:
            root = etree.parse(file)
        except Exception:
            raise InvalidSubscriptionFileError(f"'{file.name}' is not a valid YouTube export file")

        elements = root.xpath('//outline[@type="rss"]')
        channels = (_create_channel_tuple(e) for e in elements)

        for channel in channels:
            try:
                self.db.add_channel(*channel)
            except sqlite3.IntegrityError:
                pass

    def list_videos(self) -> List[Video]:
        """Returns a list of videos that match the filters set by the set_*_filter methods.

        Returns (list):
            A list of ytcc.video.Video objects
        """

        if self.search_filter:
            return self.db.search(self.search_filter)

        return self.db.get_videos(self.channel_filter, self.date_begin_filter,
                                  self.date_end_filter, self.include_watched_filter,
                                  self.config.orderby)

    def _get_filtered_video_ids(self) -> List[int]:
        return list(map(lambda video: video.id, self.list_videos()))

    def mark_watched(self, video_ids: Optional[List[int]] = None) -> List[Video]:
        """Marks the videos of channels specified in the filter as watched without playing them.
        The filters are set by the set_*_filter methods.

        Args:
            video_ids ([int]): The video IDs to mark as watched.

        Returns (list):
            A list of ytcc.video.Video objects. Contains the videos that were marked watched.
        """

        mark_ids = unpack_optional(video_ids, self._get_filtered_video_ids)
        self.db.mark_watched(mark_ids)
        return self.get_videos(mark_ids)

    def delete_channels(self, displaynames: List[str]) -> None:
        """Delete (or unsubscribe) channels.

        Args:
            displaynames (list): A list of channels' displaynames.
        """

        self.db.delete_channels(displaynames)

    def get_channels(self) -> List[Channel]:
        """Returns a list of all subscribed channels.

        Returns ([str]):
            A list of channel names.
        """

        return self.db.get_channels()

    def get_videos(self, video_ids: Iterable[int]) -> List[Video]:
        """Returns the ytcc.video.Video object for the given video IDs.

        Args:
            video_ids ([int]): the video IDs.

        Returns (list)
            A list of ytcc.video.Video objects
        """

        def resolve_ids():
            for video_id in video_ids:
                video = self.db.resolve_video_id(video_id)
                if video:
                    yield video

        return list(resolve_ids())

    def cleanup(self) -> None:
        """Deletes old videos from the database."""

        self.db.cleanup()
