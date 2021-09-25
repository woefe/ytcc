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

import datetime
import itertools
import logging
import os
from collections import defaultdict
from concurrent.futures.thread import ThreadPoolExecutor as Pool
from typing import List, Tuple, Any, Optional, Iterable, Dict

from ytcc import config, Playlist, Database, Video
from ytcc.utils import take, unpack_optional, lazy_import

youtube_dl = lazy_import("youtube_dl")

logger = logging.getLogger(__name__)

_ytdl_logger = logging.getLogger("youtube_dl")
_ytdl_logger.propagate = False
_ytdl_logger.addHandler(logging.NullHandler())
YTDL_COMMON_OPTS = {
    "logger": _ytdl_logger
}


class Fetcher:
    def __init__(self, max_backlog):
        self.max_items = max_backlog
        self.ydl_opts = {
            **YTDL_COMMON_OPTS,
            "playliststart": 1,
            "playlistend": max_backlog,
            "noplaylist": False,
            "age_limit": config.ytcc.age_limit
        }

    def get_unprocessed_entries(self, playlist: Playlist) -> Iterable[Tuple[Any, str]]:
        ydl_opts = self.ydl_opts.copy()
        ydl_opts["playlistend"] = None if playlist.reverse else self.max_items

        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            logger.info("Checking playlist '%s'...", playlist.name)
            try:
                info = ydl.extract_info(playlist.url, download=False, process=False)
            except youtube_dl.DownloadError as download_error:
                logging.error("Failed to get playlist %s. Youtube-dl said: '%s'",
                              playlist.name, download_error)
            else:
                entries = info.get("entries", [])
                if playlist.reverse:
                    entries = reversed(list(entries))
                for entry in take(self.max_items, entries):
                    e_hash = ydl._make_archive_id(entry)  # pylint: disable=protected-access
                    if e_hash is None:
                        logger.warning("Ignoring malformed playlist entry from %s", playlist.name)
                    else:
                        yield entry, e_hash

    def process_entry(self, e_hash: str, entry: Any) -> Tuple[str, Optional[Video]]:
        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            try:
                processed = ydl.process_ie_result(entry, False)
            except youtube_dl.DownloadError as download_error:
                logging.warning("Failed to get a video. Youtube-dl said: '%s'", download_error)
                return e_hash, None
            else:
                title = processed.get("title")
                if not title:
                    logger.error("Failed to process a video, because its title is missing")
                    return e_hash, None

                url = processed.get("webpage_url")
                if not url:
                    logger.error(
                        "Failed to process a video '%s', because its URL is missing",
                        title
                    )
                    return e_hash, None

                if processed.get("age_limit", 0) > config.ytcc.age_limit:
                    logger.warning("Ignoring video '%s' due to age limit", title)
                    return e_hash, None

                publish_date = 169201.0  # Minimum timestamp usable on Windows
                date_str = processed.get("upload_date")
                if date_str:
                    publish_date = datetime.datetime.strptime(date_str, "%Y%m%d").timestamp()
                else:
                    logger.warning("Publication date of video '%s' is unknown", title)

                duration = processed.get("duration") or -1
                if duration < 0:
                    logger.warning("Duration of video '%s' is unknown", title)

                thumbnail_url = processed.get("thumbnail", None)
                thumbnails = processed.get("thumbnails")
                if thumbnails:
                    thumbnail_url = self._get_highest_res_thumbnail(thumbnails).get("url")

                logger.info("Processed video '%s'", processed.get("title"))

                return e_hash, Video(
                    url=url,
                    title=title,
                    description=processed.get("description", ""),
                    publish_date=publish_date,
                    watch_date=None,
                    duration=duration,
                    thumbnail_url=thumbnail_url,
                    extractor_hash=e_hash
                )

    @staticmethod
    def _get_highest_res_thumbnail(thumbnails: List[Dict[str, Any]]) -> Dict[str, Any]:
        def _max_res(thumb: Dict[str, Any]) -> int:
            try:
                return int(thumb.get("width", 0)) * int(thumb.get("height", 0))
            except ValueError:
                return 0

        return max(thumbnails, key=_max_res, default={})

    def fetch(self, playlist: Playlist) -> Iterable[Video]:
        for entry, e_hash in self.get_unprocessed_entries(playlist):
            video = self.process_entry(e_hash, entry)[1]
            if video:
                yield video


class Updater:
    def __init__(self, db_path: str, max_backlog=20, max_fail=5):
        self.db_path = db_path
        self.max_items = max_backlog
        self.max_fail = max_fail
        self.fetcher = Fetcher(max_backlog)

    def get_new_entries(self, playlist: Playlist) -> List[Tuple[Any, str, Playlist]]:
        with Database(self.db_path) as database:
            hashes = frozenset(
                x.extractor_hash
                for x in database.list_videos(playlists=[playlist.name])
            )
            items = self.fetcher.get_unprocessed_entries(playlist)

            return [
                (entry, e_hash, playlist)
                for entry, e_hash in items
                if e_hash not in hashes
                   and database.get_extractor_fail_count(e_hash) < self.max_fail
            ]

    def update(self):
        num_workers = unpack_optional(os.cpu_count(), lambda: 1) * 4

        with Pool(num_workers) as pool, Database(self.db_path) as database:
            playlists = database.list_playlists()
            raw_entries = {}
            playlists_mapping = defaultdict(list)
            full_content = pool.map(self.get_new_entries, playlists)
            for entry, e_hash, playlist in itertools.chain.from_iterable(full_content):
                raw_entries[e_hash] = entry
                playlists_mapping[e_hash].append(playlist)

            results = dict(pool.map(self.fetcher.process_entry, *zip(*raw_entries.items())))

            for key in raw_entries:
                for playlist in playlists_mapping[key]:
                    if results[key] is not None:
                        database.add_videos([results[key]], playlist)
                    else:
                        database.increase_extractor_fail_count(key, max_fail=self.max_fail)
