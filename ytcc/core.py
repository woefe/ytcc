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
import itertools
import os
import sqlite3
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor as Pool
from typing import Iterable, List, Optional, Any, Dict, Tuple, Union

import youtube_dl
from youtube_dl import DownloadError

from ytcc import config
from ytcc.database import Database, Video, Playlist, MappedVideo, MappedPlaylist
from ytcc.exceptions import YtccException, BadURLException, DuplicateChannelException
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
    def __init__(self, db_path: str, max_backlog=20, max_fail=5):
        self.db_path = db_path
        self.max_items = max_backlog
        self.max_fail = max_fail

        self.ydl_opts = {
            "playliststart": 1,
            "playlistend": max_backlog,
            "noplaylist": False,
        }

    def get_new_entries(self, playlist: Playlist) -> List[Tuple[Any, str, Playlist]]:
        with Database(self.db_path) as database:
            hashes = frozenset(
                x.extractor_hash
                for x in database.list_videos(playlists=[playlist.name])
            )

        result = []
        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(playlist.url, download=False, process=False)
            for entry in take(self.max_items, info.get("entries", [])):
                e_hash = extractor_hash(entry)
                if e_hash not in hashes:
                    result.append((entry, e_hash, playlist))

        return result

    def process_entry(self, e_hash: str, entry: Any) -> Tuple[str, Optional[Video]]:
        with Database(self.db_path) as database:
            if database.get_extractor_fail_count(e_hash) >= self.max_fail:
                return e_hash, None

        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            try:
                processed = ydl.process_ie_result(entry, False)
                publish_date = 0.0
                date_str = processed.get("upload_date")
                if date_str:
                    publish_date = datetime.datetime.strptime(date_str, "%Y%m%d").timestamp()
                return e_hash, Video(
                    url=processed["webpage_url"],
                    title=processed["title"],
                    description=processed.get("description", ""),
                    publish_date=publish_date,
                    watched=False,
                    duration=processed.get("duration", -1),
                    extractor_hash=e_hash
                )
            except DownloadError:
                return e_hash, None

    def update(self):
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
    * ``set_channel_filter``
    * ``set_date_begin_filter``
    * ``set_date_end_filter``
    * ``set_include_watched_filter``
    """

    def __init__(self) -> None:
        self.database = Database(config.ytcc.db_path)
        self.video_id_filter: Optional[List[int]] = None
        self.playlist_filter: Optional[List[str]] = None
        self.tags_filter: Optional[List[str]] = None
        self.date_begin_filter = 0.0
        self.date_end_filter = (0.0, False)
        self.include_watched_filter: Optional[bool] = False

    def __del__(self):
        try:
            database = self.__getattribute__("database")
        except AttributeError:
            return

        database.close()

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

    def set_video_id_filter(self, ids: Optional[List[int]] = None) -> None:
        """Set the id filter.

        This filter overrides all other filters.
        :param ids: IDs to filter for.
        """
        self.video_id_filter = ids

    def set_tags_filter(self, tags: Optional[List[str]] = None) -> None:
        self.tags_filter = tags

    @staticmethod
    def update(max_fail: Optional[int] = None, max_backlog: Optional[int] = None) -> None:
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
            mpv_flags = (x for s in config.ytcc.mpv_flags.split() if (x := s.strip()))
            try:
                command = [
                    "mpv", *no_video_flag, *mpv_flags, video.url
                ]
                subprocess.run(command, check=True)
            except FileNotFoundError as fnfe:
                raise YtccException("Could not locate the mpv video player!") from fnfe
            except subprocess.CalledProcessError:
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
            "outtmpl": os.path.join(download_dir, conf.output_template),
            "ratelimit": conf.ratelimit if conf.ratelimit > 0 else None,
            "retries": conf.retries,
            "quiet": config.ytcc.loglevel == "quiet",
            "verbose": config.ytcc.loglevel == "verbose",
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
                    return False

                ydl.process_ie_result(info, download=True)
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
        except sqlite3.IntegrityError as integrity_error:
            raise DuplicateChannelException("Playlist already exists") from integrity_error

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
        self.database.mark_watched(video)

    def delete_playlist(self, name: str) -> None:
        self.database.delete_playlist(name)

    def rename_playlist(self, oldname: str, newname: str) -> None:
        self.database.rename_playlist(oldname, newname)

    def list_playlists(self) -> Iterable[MappedPlaylist]:
        return self.database.list_playlists()

    def tag_playlist(self, name: str, tags: List[str]) -> None:
        self.database.tag_playlist(name, tags)

    def cleanup(self) -> None:
        """Delete old videos from the database."""
        self.database.cleanup()
