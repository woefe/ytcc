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

import time
import datetime
import os
import subprocess
from itertools import chain
from concurrent.futures import ThreadPoolExecutor as Pool
from io import StringIO
from typing import Iterable, List, TextIO, Optional, Any, Dict
from urllib.error import URLError
from urllib.parse import urlparse, urlunparse, parse_qs
from urllib.request import urlopen

import sqlalchemy
import youtube_dl
from lxml import etree
import feedparser

from ytcc.config import Config
from ytcc.database import Channel, Database, Video
from ytcc.exceptions import YtccException, BadURLException, ChannelDoesNotExistException, \
    DuplicateChannelException, InvalidSubscriptionFileError
from ytcc.utils import unpack_optional


class Ytcc:
    """The Ytcc class handles updating the RSS feeds and playing and listing/filtering videos.

    Filters can be set with with following methods:
    * ``set_channel_filter``
    * ``set_date_begin_filter``
    * ``set_date_end_filter``
    * ``set_include_watched_filter``
    """

    def __init__(self, override_cfg_file: Optional[str] = None) -> None:
        self.config = Config(override_cfg_file)
        self.database = Database(self.config.db_path)
        self.video_id_filter: List[int] = []
        self.channel_filter: List[str] = []
        self.date_begin_filter = 0.0
        self.date_end_filter = time.mktime(time.gmtime()) + 20
        self.include_watched_filter = False

    def __enter__(self) -> "Ytcc":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        self.database.__exit__(exc_type, exc_val, exc_tb)

    def close(self) -> None:
        """Close open resources like the database connection."""
        self.database.close()

    @staticmethod
    def get_youtube_video_url(yt_videoid: Optional[str]) -> str:
        """Return the YouTube URL for the given youtube video ID.

        :param yt_videoid:  The YouTube video ID.
        :return: The YouTube URL for the given youtube video ID.
        """
        if yt_videoid is None:
            raise YtccException("Video id is none!")

        return f"https://www.youtube.com/watch?v={yt_videoid}"

    def set_channel_filter(self, channel_filter: List[str]) -> None:
        """Set the channel filter.

        The results when listing videos will only include videos by channels specified in the
        filter.

        :param channel_filter: The list of channel names.
        """
        self.channel_filter.clear()
        self.channel_filter.extend(channel_filter)

    def set_date_begin_filter(self, begin: datetime.datetime) -> None:
        """Set the time filter.

        The results when listing videos will only include videos newer than the given time.

        :param begin: The lower bound of the time filter.
        """
        self.date_begin_filter = begin.timestamp()

    def set_date_end_filter(self, end: datetime.datetime) -> None:
        """Set the time filter.

        The results when listing videos will only include videos older than the given time.

        :param end: The upper bound of the time filter.
        """
        self.date_end_filter = end.timestamp()

    def set_include_watched_filter(self) -> None:
        """Set the "watched video" filter.

        The results when listing videos will include both watched and unwatched videos.
        """
        self.include_watched_filter = True

    def set_video_id_filter(self, ids: Optional[Iterable[int]] = None) -> None:
        """Set the id filter.

        This filter overrides all other filters.
        :param ids: IDs to filter for.
        """
        self.video_id_filter.clear()
        if ids is not None:
            self.video_id_filter.extend(ids)

    @staticmethod
    def _update_channel(channel: Channel) -> List[Dict[str, Any]]:
        yt_channel_id = channel.yt_channelid
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={yt_channel_id}"
        feed = feedparser.parse(url)
        return [
            dict(
                yt_videoid=str(entry.yt_videoid),
                title=str(entry.title),
                description=str(entry.description),
                publisher=yt_channel_id,
                publish_date=time.mktime(entry.published_parsed),
                watched=False
            )
            for entry in feed.entries
        ]

    def update_all(self) -> None:
        """Check every channel for new videos."""
        channels = self.database.get_channels()
        num_workers = unpack_optional(os.cpu_count(), lambda: 1) * 2

        with Pool(num_workers) as pool:
            videos = chain.from_iterable(pool.map(self._update_channel, channels))

        self.database.add_videos(videos)

    def play_video(self, video: Video, audio_only: bool = False) -> bool:
        """Play the given video with the mpv video player and mark the the video as watched.

        The video will not be marked as watched, if the player exits unexpectedly (i.e. exits with
        non-zero exit code) or another error occurs.

        :param video: The video to play.
        :param audio_only: If True, only the audio track of the video is played
        :return: False if the given video_id does not exist or the player closed with a non-zero
         exit code. True if the video was played successfully.
        """
        no_video_flag = []
        if audio_only:
            no_video_flag.append("--no-video")

        if video:
            try:
                mpv_result = subprocess.run(["mpv", *no_video_flag, *self.config.mpv_flags,
                                             self.get_youtube_video_url(video.yt_videoid)])
            except FileNotFoundError:
                raise YtccException("Could not locate the mpv video player!")

            if mpv_result.returncode == 0:
                video.watched = True
                return True

        return False

    def download_video(self, video: Video, path: str = "", audio_only: bool = False) -> bool:
        """Download the given video with youtube-dl and mark it as watched.

        If the path is not given, the path is read from the config file.

        :param video: The video to download.
        :param path: The directory where the download is saved.
        :param audio_only: If True, only the audio track is downloaded.
        :return: True, if the video was downloaded successfully. False otherwise.
        """
        if path:
            download_dir = path
        elif self.config.download_dir:
            download_dir = self.config.download_dir
        else:
            download_dir = ""

        conf = self.config.youtube_dl

        ydl_opts: Dict[str, Any] = {
            "outtmpl": os.path.join(download_dir, conf.output_template),
            "ratelimit": conf.ratelimit,
            "retries": conf.retries,
            "quiet": conf.loglevel == "quiet",
            "verbose": conf.loglevel == "verbose",
            "ignoreerrors": False
        }

        if audio_only:
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
            url = self.get_youtube_video_url(video.yt_videoid)
            try:
                info = ydl.extract_info(url, download=False, process=False)
                if info.get("is_live", False) and conf.skip_live_stream:
                    return False

                ydl.process_ie_result(info, download=True)
                video.watched = True
                return True
            except youtube_dl.utils.YoutubeDLError:
                return False

    def add_channel(self, displayname: str, channel_url: str) -> None:
        """Subscribe to a channel.

        :param displayname: A human readable name of the channel.
        :param channel_url: The url to a page that can identify the channel.
        :raises ChannelDoesNotExistException: If the given URL does not exist.
        :raises DuplicateChannelException: If the channel already exists in the database.
        :raises BadURLException: If the given URL does not refer to a YouTube channel.
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
            self.database.add_channel(Channel(displayname=displayname, yt_channelid=yt_channelid))
        except sqlalchemy.exc.IntegrityError:
            raise DuplicateChannelException(f"Channel already subscribed: {displayname}")

    def import_channels(self, file: TextIO) -> None:
        """Import all channels from YouTube's subscription export file.

        :param file: The file to read from.
        """
        def _create_channel(elem: etree.Element) -> Channel:
            rss_url = urlparse(elem.attrib["xmlUrl"])
            query_dict = parse_qs(rss_url.query, keep_blank_values=False)
            channel_id = query_dict.get("channel_id", [])
            if len(channel_id) != 1:
                message = f"'{file.name}' is not a valid YouTube export file"
                raise InvalidSubscriptionFileError(message)
            return Channel(displayname=elem.attrib["title"], yt_channelid=channel_id[0])

        try:
            root = etree.parse(file)
        except Exception:
            raise InvalidSubscriptionFileError(f"'{file.name}' is not a valid YouTube export file")

        elements = root.xpath('//outline[@type="rss"]')
        self.database.add_channels((_create_channel(e) for e in elements))

    def list_videos(self) -> List[Video]:
        """Return a list of videos that match the filters set by the set_*_filter methods.

        :return: A list of videos.
        """
        if self.video_id_filter:
            return self.database.session.query(Video) \
                .join(Channel, Channel.yt_channelid == Video.publisher) \
                .filter(Video.id.in_(self.video_id_filter)) \
                .order_by(*self.config.order_by).all()

        query = self.database.session.query(Video) \
            .join(Channel, Channel.yt_channelid == Video.publisher) \
            .filter(Video.publish_date > self.date_begin_filter) \
            .filter(Video.publish_date < self.date_end_filter)

        if self.channel_filter:
            query = query.filter(Channel.displayname.in_(self.channel_filter))

        if not self.include_watched_filter:
            query = query.filter(~Video.watched)

        query = query.order_by(*self.config.order_by)
        return query.all()

    def delete_channels(self, displaynames: List[str]) -> None:
        """Delete (or unsubscribe) channels.

        :param displaynames: The names of channels to delete.
        """
        self.database.delete_channels(displaynames)

    def get_channels(self) -> List[Channel]:
        """Get the list of all subscribed channels.

        :return: A list of channel names.
        """
        return self.database.get_channels()

    def cleanup(self) -> None:
        """Delete old videos from the database."""
        self.database.cleanup()
