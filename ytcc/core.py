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

import datetime
import itertools
import logging
import os
import sqlite3
import subprocess
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor as Pool
from pathlib import Path
from typing import Iterable, List, Optional, Any, Dict, Tuple, Union
from urllib.parse import parse_qs, urlparse

from ytcc import config
from ytcc.database import Database, Video, Playlist, MappedVideo, MappedPlaylist
from ytcc.exceptions import YtccException, BadURLException, NameConflictError, \
    PlaylistDoesNotExistException, InvalidSubscriptionFileError
from ytcc.utils import unpack_optional, take, lazy_import

youtube_dl = lazy_import("youtube_dl")

YTDL_COMMON_OPTS = {
    "logger": logging.getLogger("youtube_dl")
}

logger = logging.getLogger(__name__)


class Updater:
    def __init__(self, db_path: str, max_backlog=20, max_fail=5):
        """
        Initialize db

        Args:
            self: (todo): write your description
            db_path: (str): write your description
            max_backlog: (int): write your description
            max_fail: (int): write your description
        """
        self.db_path = db_path
        self.max_items = max_backlog
        self.max_fail = max_fail

        self.ydl_opts = {
            **YTDL_COMMON_OPTS,
            "playliststart": 1,
            "playlistend": max_backlog,
            "noplaylist": False,
            "age_limit": config.ytcc.age_limit
        }

    def get_new_entries(self, playlist: Playlist) -> List[Tuple[Any, str, Playlist]]:
        """
        Return list of entries.

        Args:
            self: (todo): write your description
            playlist: (list): write your description
        """
        with Database(self.db_path) as database:
            hashes = frozenset(
                x.extractor_hash
                for x in database.list_videos(playlists=[playlist.name])
            )

        result = []
        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            logger.info("Checking playlist '%s'...", playlist.name)
            try:
                info = ydl.extract_info(playlist.url, download=False, process=False)
            except youtube_dl.DownloadError as download_error:
                logging.error("Failed to get playlist %s. Youtube-dl said: '%s'",
                              playlist.name, download_error)
            else:
                for entry in take(self.max_items, info.get("entries", [])):
                    e_hash = ydl._make_archive_id(entry)  # pylint: disable=protected-access
                    if e_hash not in hashes:
                        result.append((entry, e_hash, playlist))

        return result

    def process_entry(self, e_hash: str, entry: Any) -> Tuple[str, Optional[Video]]:
        """
        Process a single entry.

        Args:
            self: (todo): write your description
            e_hash: (todo): write your description
            entry: (todo): write your description
        """
        with Database(self.db_path) as database:
            if database.get_extractor_fail_count(e_hash) >= self.max_fail:
                return e_hash, None

        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            try:
                processed = ydl.process_ie_result(entry, False)
            except youtube_dl.DownloadError as download_error:
                logging.warning("Failed to get a video. Youtube-dl said: '%s'", download_error)
                return e_hash, None
            else:
                publish_date = 0.0
                date_str = processed.get("upload_date")
                if date_str:
                    publish_date = datetime.datetime.strptime(date_str, "%Y%m%d").timestamp()

                if processed.get("age_limit", 0) > config.ytcc.age_limit:
                    logger.warning("Ignoring video '%s' due to age limit", processed.get("title"))
                    return e_hash, None

                logger.info("Processed video '%s'", processed.get("title"))

                return e_hash, Video(
                    url=processed["webpage_url"],
                    title=processed["title"],
                    description=processed.get("description", ""),
                    publish_date=publish_date,
                    watched=False,
                    duration=processed.get("duration", -1),
                    extractor_hash=e_hash
                )

    def update(self):
        """
        Update list of the entries.

        Args:
            self: (todo): write your description
        """
        num_workers = unpack_optional(os.cpu_count(), lambda: 1) * 4

        with Pool(num_workers) as pool, Database(self.db_path) as database:
            playlists = database.list_playlists()
            raw_entries = dict()
            playlists_mapping = defaultdict(list)
            full_content = pool.map(self.get_new_entries, playlists)
            for entry, e_hash, playlist in itertools.chain.from_iterable(full_content):
                raw_entries[e_hash] = entry
                playlists_mapping[e_hash].append(playlist)

            results = dict(pool.map(self.process_entry, *zip(*raw_entries.items())))

            for key in raw_entries:
                for playlist in playlists_mapping[key]:
                    if results[key] is not None:
                        database.add_videos([results[key]], playlist)
                    else:
                        database.increase_extractor_fail_count(key, max_fail=self.max_fail)


class Ytcc:
    """The Ytcc class handles updating the RSS feeds and playing and listing/filtering videos.

    Filters can be set with with following methods:
    * ``set_set_playlist_filter``
    * ``set_date_begin_filter``
    * ``set_date_end_filter``
    * ``set_include_watched_filter``
    * ``set_set_video_id_filter``
    * ``set_tags_set_tags_filter``
    """

    def __init__(self) -> None:
        """
        Initialize video.

        Args:
            self: (todo): write your description
        """
        self._database: Optional[Database] = None
        self.video_id_filter: Optional[List[int]] = None
        self.playlist_filter: Optional[List[str]] = None
        self.tags_filter: Optional[List[str]] = None
        self.date_begin_filter = 0.0
        self.date_end_filter = (0.0, False)
        self.include_watched_filter: Optional[bool] = False

    def __enter__(self) -> "Ytcc":
        """
        Returns the current request.

        Args:
            self: (todo): write your description
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        """
        Called when the given exception is raised.

        Args:
            self: (todo): write your description
            exc_type: (todo): write your description
            exc_val: (todo): write your description
            exc_tb: (todo): write your description
        """
        if self._database is not None:
            self._database.__exit__(exc_type, exc_val, exc_tb)

    @property
    def database(self) -> Database:
        """
        Returns the database.

        Args:
            self: (todo): write your description
        """
        if self._database is None:
            self._database = Database(config.ytcc.db_path)
        return self._database

    def close(self) -> None:
        """Close open resources like the database connection."""
        self.database.close()

    def set_playlist_filter(self, playlists: List[str]) -> None:
        """Set the channel filter.

        The results when listing videos will only include videos by channels specified in the
        filter.

        :param playlists: The list of channel names.
        """
        self.playlist_filter = playlists

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
        self.date_end_filter = (end.timestamp(), True)

    def set_include_watched_filter(self, enabled: bool = False) -> None:
        """Set the "watched video" filter.

        The results when listing videos will include both watched and unwatched videos.
        """
        self.include_watched_filter = None if enabled else False

    def set_video_id_filter(self, ids: Optional[List[int]] = None) -> None:
        """Set the id filter.

        The results will have the given ids. This filter should in most cases be combined with the
        `set_include_watched_filter()`
        :param ids: IDs to filter for.
        """
        self.video_id_filter = ids

    def set_tags_filter(self, tags: Optional[List[str]] = None) -> None:
        """Set the tag filter.

        The results of ``list_videos()`` will include only playlists tagged with at least one of
        the given tags.

        :param tags: The tags of playlists to include in the result
        """
        self.tags_filter = tags

    @staticmethod
    def update(max_fail: Optional[int] = None, max_backlog: Optional[int] = None) -> None:
        """
        Update db db backlogor.

        Args:
            max_fail: (int): write your description
            max_backlog: (int): write your description
        """
        Updater(
            db_path=config.ytcc.db_path,
            max_fail=max_fail or config.ytcc.max_update_fail,
            max_backlog=max_backlog or config.ytcc.max_update_backlog
        ).update()

    @staticmethod
    def play_video(video: Video, audio_only: bool = False) -> bool:
        """Play the given video with the mpv video player.

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
            mpv_flags = filter(bool, map(str.strip, config.ytcc.mpv_flags.split()))
            try:
                command = [
                    "mpv", *no_video_flag, *mpv_flags, video.url
                ]
                subprocess.run(command, check=True)
            except FileNotFoundError as fnfe:
                raise YtccException("Could not locate the mpv video player!") from fnfe
            except subprocess.CalledProcessError as cpe:
                logger.debug("MPV failed! Command: %s; Stdout: %s; Stderr %s; Returncode: %s",
                             cpe.cmd, cpe.stdout, cpe.stderr, cpe.returncode)
                return False

            return True

        return False

    @staticmethod
    def download_video(video: Video, path: str = "", audio_only: bool = False) -> bool:
        """Download the given video with youtube-dl.

        If the path is not given, the path is read from the config file.

        :param video: The video to download.
        :param path: The directory where the download is saved.
        :param audio_only: If True, only the audio track is downloaded.
        :return: True, if the video was downloaded successfully. False otherwise.
        """
        if path:
            download_dir = path
        elif config.ytcc.download_dir:
            download_dir = config.ytcc.download_dir
        else:
            download_dir = ""

        conf = config.youtube_dl

        ydl_opts: Dict[str, Any] = {
            **YTDL_COMMON_OPTS,
            "outtmpl": os.path.join(download_dir, conf.output_template),
            "ratelimit": conf.ratelimit if conf.ratelimit > 0 else None,
            "retries": conf.retries,
            "merge_output_format": conf.merge_output_format,
            "ignoreerrors": False,
            "postprocessors": [
                {
                    "key": "FFmpegMetadata"
                }
            ]
        }

        if audio_only:
            ydl_opts["format"] = "bestaudio/best"
            if conf.thumbnail:
                ydl_opts["writethumbnail"] = True
                extract_audio_pp = {'key': 'FFmpegExtractAudio', 'preferredcodec': "m4a"}
                ydl_opts["postprocessors"].insert(0, extract_audio_pp)
                ydl_opts["postprocessors"].append({"key": "EmbedThumbnail"})
        else:
            ydl_opts["format"] = conf.format
            if conf.subtitles != ["off"]:
                ydl_opts["subtitleslangs"] = conf.subtitles
                ydl_opts["writesubtitles"] = True
                ydl_opts["writeautomaticsub"] = True
                ydl_opts["postprocessors"].append({"key": "FFmpegEmbedSubtitle"})

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(video.url, download=False, process=False)
                if info.get("is_live", False) and conf.skip_live_stream:
                    logger.info("Skipping livestream %s", video.url)
                    return False

                ydl.process_ie_result(info, download=True)
                return True
            except youtube_dl.utils.YoutubeDLError as ydl_err:
                logger.debug("youtube-dl failed with '%s'", ydl_err)
                return False

    def add_playlist(self, name: str, url: str) -> None:
        """
        Add a new playlist.

        Args:
            self: (todo): write your description
            name: (str): write your description
            url: (str): write your description
        """
        ydl_opts = {
            **YTDL_COMMON_OPTS,
            "playliststart": 1,
            "playlistend": 2,
            "noplaylist": False,
            "extract_flat": "in_playlist"
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False, process=True)
            except youtube_dl.utils.DownloadError as download_error:
                logger.debug(
                    "'%s' is not supported by youtube-dl. Youtube-dl's error: '%s'",
                    url,
                    download_error
                )
                raise BadURLException(
                    "URL is not supported by youtube-dl or does not exist"
                ) from download_error

            if not info.get("_type") == "playlist":
                logger.debug(
                    "'%s' doesn't seem point to a playlist. Extractor info is: '%s'",
                    url,
                    info
                )
                raise BadURLException("Not a playlist or not supported by youtube-dl")

        try:
            real_url = info.get("webpage_url")
            if real_url:
                self.database.add_playlist(name, real_url)
        except sqlite3.IntegrityError as integrity_error:
            logger.debug(
                "Cannot subscribe to playlist due to integrity constraint error: %s",
                integrity_error
            )
            raise NameConflictError("Playlist already exists") from integrity_error

    def list_videos(self) -> Iterable[MappedVideo]:
        """Return a list of videos that match the filters set by the set_*_filter methods.

        :return: A list of videos.
        """
        if not self.date_end_filter[1]:
            date_end_filter = time.mktime(time.gmtime()) + 20
        else:
            date_end_filter = self.date_end_filter[0]

        return self.database.list_videos(
            since=self.date_begin_filter,
            till=date_end_filter,
            watched=self.include_watched_filter,
            tags=self.tags_filter,
            playlists=self.playlist_filter,
            ids=self.video_id_filter
        )

    def mark_watched(self, video: Union[List[int], int, MappedVideo]) -> None:
        """
        Mark the video.

        Args:
            self: (todo): write your description
            video: (todo): write your description
            Union: (str): write your description
            List: (todo): write your description
            int: (todo): write your description
            int: (todo): write your description
            MappedVideo: (todo): write your description
        """
        self.database.mark_watched(video)

    def delete_playlist(self, name: str) -> None:
        """
        Delete a playlist.

        Args:
            self: (todo): write your description
            name: (str): write your description
        """
        if not self.database.delete_playlist(name):
            raise PlaylistDoesNotExistException(f"Could not remove playlist {name}, because "
                                                "it does not exist")

    def rename_playlist(self, oldname: str, newname: str) -> None:
        """
        Rename a playlist.

        Args:
            self: (todo): write your description
            oldname: (str): write your description
            newname: (str): write your description
        """
        if not self.database.rename_playlist(oldname, newname):
            raise NameConflictError("Renaming failed. Either the old name does not exist or the "
                                    "new name is already used.")

    def list_playlists(self) -> Iterable[MappedPlaylist]:
        """
        List playlists.

        Args:
            self: (todo): write your description
        """
        return self.database.list_playlists()

    def tag_playlist(self, name: str, tags: List[str]) -> None:
        """
        Get a list of a playlist.

        Args:
            self: (todo): write your description
            name: (str): write your description
            tags: (todo): write your description
        """
        self.database.tag_playlist(name, tags)

    def list_tags(self) -> Iterable[str]:
        """
        List all tags.

        Args:
            self: (todo): write your description
        """
        return self.database.list_tags()

    def cleanup(self, keep: int) -> None:
        """Delete old videos from the database.

        :param keep: The number of videos to keep
        :return: None
        """
        self.database.cleanup(keep)

    def import_yt_opml(self, file: Path):
        """
        Parse channel options.

        Args:
            self: (todo): write your description
            file: (str): write your description
        """
        def _from_xml_element(elem: ET.Element) -> Tuple[str, str]:
            """
            Create an xml element from an xml element.

            Args:
                elem: (todo): write your description
                ET: (todo): write your description
                Element: (todo): write your description
            """
            rss_url = urlparse(elem.attrib["xmlUrl"])
            query_dict = parse_qs(rss_url.query, keep_blank_values=False)
            channel_id = query_dict.get("channel_id", [])
            if len(channel_id) != 1:
                message = f"'{str(file)}' is not a valid YouTube export file"
                raise InvalidSubscriptionFileError(message)
            yt_url = f"https://www.youtube.com/channel/{channel_id[0]}/videos"
            return elem.attrib["title"], yt_url

        try:
            tree = ET.parse(file)
        except ET.ParseError as err:
            raise InvalidSubscriptionFileError(
                f"'{str(file)}' is not a valid YouTube export file"
            ) from err
        except OSError as err:
            raise InvalidSubscriptionFileError(f"{str(file)} cannot be accessed") from err

        root = tree.getroot()
        for element in root.findall('.//outline[@type="rss"]'):
            name, url = _from_xml_element(element)
            try:
                self.add_playlist(name, url)
            except NameConflictError:
                logger.warning("Ignoring playlist '%s', because it already subscribed", name)
            except BadURLException:
                logger.warning("Ignoring playlist '%s', "
                               "because it is not supported by youtube-dl", name)
            else:
                logger.info("Added playlist '%s'", name)
