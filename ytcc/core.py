# ytcc - The YouTube channel checker
# Copyright (C) 2021  Wolfgang Popp
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
import asyncio
import csv
import datetime
import logging
import os
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, List, Optional, Any, Dict, Tuple, Union
from urllib.parse import parse_qs, urlparse

from ytcc import config
from ytcc.config import Direction, VideoAttr
from ytcc.database import Database, Video, MappedVideo, MappedPlaylist, Playlist
from ytcc.exceptions import YtccException, BadURLException, NameConflictError, \
    PlaylistDoesNotExistException, InvalidSubscriptionFileError
from ytcc.updater import Updater, Fetcher, YTDL_COMMON_OPTS, make_archive_id
from ytcc.utils import lazy_import

youtube_dl = lazy_import("yt_dlp", "youtube_dl")

logger = logging.getLogger(__name__)


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
        self._database: Optional[Database] = None
        self.video_id_filter: Optional[List[int]] = None
        self.playlist_filter: Optional[List[str]] = None
        self.tags_filter: Optional[List[str]] = None
        self.date_begin_filter: Optional[float] = None
        self.date_end_filter: Optional[float] = None
        self.include_watched_filter: Optional[bool] = False
        self.order_by: Optional[List[Tuple[VideoAttr, Direction]]] = None

    def __enter__(self) -> "Ytcc":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        if self._database is not None:
            self._database.__exit__(exc_type, exc_val, exc_tb)

    @property
    def database(self) -> Database:
        if self._database is None:
            self._database = Database(config.ytcc.db_path)
        return self._database

    def close(self) -> None:
        """Close open resources like the database connection."""
        if self._database is not None:
            self._database.close()

    def set_playlist_filter(self, playlists: Optional[List[str]]) -> None:
        """Set the channel filter.

        The results when listing videos will only include videos by channels specified in the
        filter.

        :param playlists: The list of channel names.
        """
        self.playlist_filter = playlists

    def set_date_begin_filter(self, begin: Optional[datetime.datetime]) -> None:
        """Set the time filter.

        The results when listing videos will only include videos newer than the given time.

        :param begin: The lower bound of the time filter.
        """
        if begin is not None:
            self.date_begin_filter = begin.timestamp()

    def set_date_end_filter(self, end: Optional[datetime.datetime]) -> None:
        """Set the time filter.

        The results when listing videos will only include videos older than the given time.

        :param end: The upper bound of the time filter.
        """
        if end is not None:
            self.date_end_filter = end.timestamp()

    def set_watched_filter(self, enabled: Optional[bool] = False) -> None:
        """Set the "watched video" filter.

        The results when listing videos will include both watched and unwatched videos.

        :param enabled: If None, all videos ar listed. If True, only watched videos are listed.
                        If False, only unwatched are listed
        """
        self.include_watched_filter = enabled

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

    def set_listing_order(self, order_by: List[Tuple[VideoAttr, Direction]]):
        self.order_by = order_by

    @staticmethod
    def update(max_fail: Optional[int] = None, max_backlog: Optional[int] = None) -> None:
        with Updater(
            db_path=config.ytcc.db_path,
            max_fail=max_fail or config.ytcc.max_update_fail,
            max_backlog=max_backlog or config.ytcc.max_update_backlog
        ) as updater:
            updater.update()

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
    def download_video(video: MappedVideo, path: str = "", audio_only: bool = False,
                       subdirs: Optional[bool] = None) -> bool:
        """Download the given video.

        If the path is not given, the path is read from the config file.

        :param video: The video to download.
        :param path: The directory where the download is saved.
        :param audio_only: If True, only the audio track is downloaded.
        :param subdirs: Overrides config.ytcc.download_subdirs if not None.
        :return: True, if the video was downloaded successfully. False otherwise.
        """
        class GetFilenameProcessor(youtube_dl.postprocessor.common.PostProcessor):  # type: ignore
            def __init__(self):
                super().__init__()
                self.actual_file = None

            def run(self, information):
                self.actual_file = information.get("filepath")
                return [], information

            def report_progress(self, *args, **kwargs):
                pass

        filename_processor = GetFilenameProcessor()

        if 0 < config.youtube_dl.max_duration < video.duration:
            logger.info(
                "Skipping video %s, because it is longer than the configured maximum",
                video.url
            )
            return False

        download_dir = Path(path or config.ytcc.download_dir or "").expanduser()
        subdir = ""
        symlink_dirs = []
        if (subdirs if subdirs is not None else config.ytcc.download_subdirs) and video.playlists:
            subdir = video.playlists[0].name
            symlink_dirs = [
                download_dir / pl.name for pl in video.playlists[1:]
            ]

        with youtube_dl.YoutubeDL(Ytcc._ydl_opts(str(download_dir), subdir, audio_only)) as ydl:
            try:
                # pylint: disable=protected-access
                if isinstance(ydl._pps, list):
                    ydl._pps.append(filename_processor)
                elif isinstance(ydl._pps, dict):
                    ydl.add_post_processor(filename_processor, when="post_process")
                info = ydl.extract_info(video.url, download=False, process=False)
                if info.get("is_live", False) and config.youtube_dl.skip_live_stream:
                    logger.info("Skipping livestream %s", video.url)
                    return False

                ydl.process_ie_result(info, download=True)
            except youtube_dl.utils.YoutubeDLError as ydl_err:
                logger.debug("Download failed with '%s'", ydl_err)
                return False

            actual_file = Path(filename_processor.actual_file).expanduser()
            if actual_file:
                logger.debug("Downloaded '%s' to '%s'", video.title, str(actual_file))
                for link_dir in symlink_dirs:
                    link_dir.mkdir(parents=True, exist_ok=True)
                    destination = link_dir / actual_file.relative_to(download_dir / subdir)
                    try:
                        destination.symlink_to(actual_file)
                        logger.info("Symlinked '%s' to '%s'", actual_file, link_dir)
                    except FileExistsError:
                        logger.debug("Skipping symlink, because it already exists")

            return True

    @staticmethod
    def _ydl_opts(download_dir: str, subdir: str, audio_only: bool) -> Dict[str, Any]:
        conf = config.youtube_dl

        ydl_opts: Dict[str, Any] = {
            **YTDL_COMMON_OPTS,
            "outtmpl": os.path.join(download_dir, subdir, conf.output_template),
            "ratelimit": conf.ratelimit if conf.ratelimit > 0 else None,
            "retries": conf.retries,
            "merge_output_format": conf.merge_output_format,
            "restrictfilenames": conf.restrict_filenames,
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

        return ydl_opts

    @staticmethod
    def _is_playlist_reverse(items: List[Video]) -> bool:
        if not items or items[0].publish_date >= items[-1].publish_date:
            return False

        prev = items[0]
        for item in items:
            if prev.publish_date > item.publish_date:
                return False
            prev = item

        return True

    def add_playlist(self, name: str, url: str, reverse: bool = False,
                     skip_update_check: bool = False) -> None:
        ydl_opts = {
            **YTDL_COMMON_OPTS,
            "playliststart": 1,
            "playlistend": 10,
            "noplaylist": False,
            "extract_flat": "in_playlist"
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False, process=True)
            except youtube_dl.utils.DownloadError as download_error:
                logger.debug(
                    "'%s' is not supported. Encountered error: '%s'",
                    url,
                    download_error
                )
                raise BadURLException(
                    "URL is not supported or does not exist"
                ) from download_error

            if info.get("_type") != "playlist":
                logger.debug(
                    "'%s' doesn't seem point to a playlist. Extractor info is: '%s'",
                    url,
                    info
                )
                raise BadURLException("Not a playlist or not supported")

            peek = list(info.get("entries"))
            for entry in peek:
                if make_archive_id(ydl, entry) is None:
                    raise BadURLException("The given URL is not supported by ytcc, because it "
                                          "doesn't point to a playlist")

            real_url = info.get("webpage_url")
            if not real_url:
                raise BadURLException("The playlist URL cannot be found")

            if not skip_update_check:
                logger.info("Performing update check on 10 playlist items")
                playlist = asyncio.run(Fetcher(10).fetch(Playlist(name, real_url, reverse)))
                if not playlist:
                    logger.warning("The playlist might be empty")

                if self._is_playlist_reverse(playlist):
                    logger.warning(
                        "The playlist seems to be updated in opposite order. You probably won't "
                        "receive any updates for this playlist. Use `ytcc reverse '%s'` to change "
                        "the update behavior of the playlist.",
                        name
                    )

        try:
            self.database.add_playlist(name, real_url, reverse)
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
        return self.database.list_videos(
            since=self.date_begin_filter,
            till=self.date_end_filter,
            watched=self.include_watched_filter,
            tags=self.tags_filter,
            playlists=self.playlist_filter,
            ids=self.video_id_filter,
            order_by=self.order_by
        )

    def mark_watched(self, video: Union[List[int], int, MappedVideo]) -> None:
        self.database.mark_watched(video)

    def mark_unwatched(self, video: Union[List[int], int, MappedVideo]) -> None:
        self.database.mark_unwatched(video)

    def unmark_recent(self):
        videos = list(self.database.list_videos(
            watched=True,
            order_by=[(VideoAttr.WATCHED, Direction.DESC)]
        ))
        if videos:
            self.mark_unwatched(videos[0])

    def delete_playlist(self, name: str) -> None:
        if not self.database.delete_playlist(name):
            raise PlaylistDoesNotExistException(f"Could not remove playlist {name}, because "
                                                "it does not exist")

    def rename_playlist(self, oldname: str, newname: str) -> None:
        if not self.database.rename_playlist(oldname, newname):
            raise NameConflictError("Renaming failed. Either the old name does not exist or the "
                                    "new name is already used.")

    def reverse_playlist(self, playlist: str) -> None:
        if not self.database.reverse_playlist(playlist):
            raise PlaylistDoesNotExistException(
                "Could not modify the playlist, because it does not exist"
            )

    def list_playlists(self) -> Iterable[MappedPlaylist]:
        return self.database.list_playlists()

    def tag_playlist(self, name: str, tags: List[str]) -> None:
        self.database.tag_playlist(name, tags)

    def list_tags(self) -> Iterable[str]:
        return self.database.list_tags()

    def cleanup(self, keep: int) -> None:
        """Delete old videos from the database.

        :param keep: The number of videos to keep
        :return: None
        """
        self.database.cleanup(keep)

    def import_yt_opml(self, file: Path):
        def _from_xml_element(elem: ET.Element) -> Tuple[str, str]:
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
        subscriptions = (
            _from_xml_element(element)
            for element in root.findall('.//outline[@type="rss"]')
        )
        self._bulk_subscribe(subscriptions)

    def import_yt_csv(self, file: Path):
        with open(file, newline='', encoding="utf-8") as csvfile:
            sample = csvfile.read(4096)
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample)

            csvfile.seek(0)
            rows = csv.reader(csvfile, dialect)

            if sniffer.has_header(sample):
                next(rows, None)

            subscriptions = []
            for row in rows:
                # Ignore empty lines
                if not row:
                    continue

                if len(row) != 3:
                    raise InvalidSubscriptionFileError(
                        f"{str(file)} has an invalid number of columns. Expecting: ID, URL, Name"
                    )

                yt_url = f"https://www.youtube.com/channel/{row[0]}/videos"
                subscriptions.append((row[2], yt_url))

            self._bulk_subscribe(subscriptions)

    def _bulk_subscribe(self, subscriptions: Iterable[Tuple[str, str]]) -> None:
        for name, url in subscriptions:
            try:
                self.add_playlist(name, url, skip_update_check=True)
            except NameConflictError:
                logger.warning("Ignoring playlist '%s', because it already subscribed", name)
            except BadURLException:
                logger.warning("Ignoring playlist '%s', because it is not supported", name)
            else:
                logger.info("Added playlist '%s'", name)
