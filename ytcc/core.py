# ytcc - The YouTube channel checker
# Copyright (C) 2019  Wolfgang Popp
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
import hashlib
import logging
import os
import sqlite3
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor as Pool
from typing import Iterable, List, Optional, Any, Dict, FrozenSet, Tuple

import youtube_dl
from youtube_dl import DownloadError

from ytcc.config import Config
from ytcc.database import Database, Video, Playlist, MappedVideo
from ytcc.exceptions import YtccException, BadURLException, DuplicateChannelException, \
    DatabaseOperationalError
from ytcc.utils import unpack_optional, take


def extractor_hash(data: Dict[str, str]) -> str:
    digest = hashlib.sha256()
    for key in sorted(data.keys()):
        digest.update(key.encode("utf-8"))
        digest.update(data[key].encode("utf-8"))
    return digest.hexdigest()


def get_url(entry):
    url = entry.get("url")
    if entry.get("ie_key") == "Youtube":
        return f"https://www.youtube.com/watch?v={entry.get('id')}"
    if not any(map(url.startswith, ("http://", "https://", "ftp://", "ftps://"))):
        return None
    return url


class Updater:
    db_path = None
    max_items = 20
    ydl_opts = {
        "playliststart": 1,
        "playlistend": max_items,
        "noplaylist": False,
    }

    @staticmethod
    def get_new_entries(playlist: Playlist) -> List[Tuple[Any, str]]:
        with Database(Updater.db_path) as db:
            hashes = frozenset(x.extractor_hash for x in db.list_videos(playlists=[playlist.name]))

        result = []
        with youtube_dl.YoutubeDL(Updater.ydl_opts) as ydl:
            info = ydl.extract_info(playlist.url, download=False, process=False)
            for entry in take(Updater.max_items, info.get("entries", [])):
                h = extractor_hash(entry)
                if h not in hashes:
                    result.append((entry, h))

        return result

    @staticmethod
    def process_entry(entry, extractor_hash, playlist) -> Optional[Tuple[Playlist, Video]]:
        with youtube_dl.YoutubeDL(Updater.ydl_opts) as ydl:
            try:
                processed = ydl.process_ie_result(entry, False)
                return playlist, Video(
                    url=processed["webpage_url"],
                    title=processed["title"],
                    description=processed.get("description", ""),
                    publish_date=processed.get("upload_date", ""),
                    watched=False,
                    duration=processed.get("duration", -1),
                    extractor_hash=extractor_hash
                )
            except DownloadError as dl:
                #logging.error(dl)
                return None


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
        self.video_id_filter: Optional[List[int]] = None
        self.playlist_filter: Optional[List[str]] = None
        self.tags_filter: Optional[List[str]] = None
        self.date_begin_filter = 0.0
        self.date_end_filter = (0.0, False)
        self.include_watched_filter = False

    def __del__(self):
        try:
            db = self.__getattribute__("database")
        except AttributeError:
            return

        db.close()

    def __enter__(self) -> "Ytcc":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        self.database.__exit__(exc_type, exc_val, exc_tb)

    def close(self) -> None:
        """Close open resources like the database connection."""
        self.database.close()

    def set_playlist_filter(self, channel_filter: List[str]) -> None:
        """Set the channel filter.

        The results when listing videos will only include videos by channels specified in the
        filter.

        :param channel_filter: The list of channel names.
        """
        self.playlist_filter = channel_filter

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

    def set_video_id_filter(self, ids: Optional[Iterable[int]] = None) -> None:
        """Set the id filter.

        This filter overrides all other filters.
        :param ids: IDs to filter for.
        """
        self.video_id_filter = ids

    def set_tags_filter(self, tags: Optional[List[str]] = None) -> None:
        self.tags_filter = tags

    def update(self) -> None:

        playlists = list(self.database.list_playlists())
        num_workers = unpack_optional(os.cpu_count(), lambda: 1) * 4
        Updater.db_path = self.config.db_path

        with Pool(num_workers) as pool:
            entries = list(pool.map(Updater.get_new_entries, playlists))
            new_entries = [
                (entry, e_hash, playlist)
                for playlist, updates in zip(playlists, entries)
                for entry, e_hash in updates
            ]
            updates = [x for x in pool.map(Updater.process_entry, *zip(*new_entries)) if x]

        with Database(Updater.db_path) as db:
            for playlist, update in updates:
                db.add_videos([update], playlist)

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
                command = [
                    "mpv", *no_video_flag, *self.config.mpv_flags, video.url
                ]
                subprocess.run(command, check=True)
            except FileNotFoundError:
                raise YtccException("Could not locate the mpv video player!")
            except subprocess.CalledProcessError:
                return False

            video.watched = True
            # TODO
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
            if conf.subtitles != "off":
                ydl_opts["subtitleslangs"] = list(map(str.strip, conf.subtitles.split(",")))
                ydl_opts["writesubtitles"] = True
                ydl_opts["writeautomaticsub"] = True
                ydl_opts["postprocessors"].append({"key": "FFmpegEmbedSubtitle"})

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(video.url, download=False, process=False)
                if info.get("is_live", False) and conf.skip_live_stream:
                    return False

                ydl.process_ie_result(info, download=True)
                # TODO
                video.watched = True
                return True
            except youtube_dl.utils.YoutubeDLError:
                return False

    def add_playlist(self, name: str, url: str) -> None:
        ydl_opts = {
            "playliststart": 1,
            "playlistend": 2,
            "noplaylist": False,
            "extract_flat": "in_playlist"
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False, process=True)
            if not info.get("_type") == "playlist":
                raise BadURLException("Not a playlist or not supported by youtube-dl")

        try:
            real_url = info.get("webpage_url")
            if real_url:
                self.database.add_playlist(name, real_url)
            # TODO
        except:
            raise DuplicateChannelException("Playlist already exists")

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

    def delete_playlist(self, name: str) -> None:
        self.database.delete_playlist(name)

    def rename_playlist(self, oldname: str, newname: str) -> None:
        self.database.rename_playlist(oldname, newname)

    def list_playlists(self) -> Iterable[Playlist]:
        return self.database.list_playlists()

    def cleanup(self) -> None:
        """Delete old videos from the database."""
        self.database.cleanup()
