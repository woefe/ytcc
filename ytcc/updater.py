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
import datetime
import hashlib
import itertools
import logging
from functools import partial
from typing import List, Tuple, Any, Optional, Iterable, Dict, TYPE_CHECKING

from ytcc import config, Playlist, Database, Video
from ytcc.utils import take, lazy_import

if TYPE_CHECKING:
    try:
        from yt_dlp import YoutubeDL  # pylint: disable=unused-import
    except ImportError:
        from youtube_dl import YoutubeDL

youtube_dl = lazy_import("yt_dlp", "youtube_dl")

logger = logging.getLogger(__name__)

_ytdl_logger = logging.getLogger("youtube_dl")
_ytdl_logger.propagate = False
_ytdl_logger.addHandler(logging.NullHandler())
YTDL_COMMON_OPTS = {
    "logger": _ytdl_logger
}


def make_archive_id(ydl: "YoutubeDL", entry: Dict[str, Any]) -> Optional[str]:
    # pylint: disable=protected-access
    archive_id = ydl._make_archive_id(entry)
    entry_type = entry.get("_type", "").lower()
    if archive_id is None and entry.get("url") and entry_type in ("url", "url_transparent"):
        entry = entry.copy()
        plain_url, _ = youtube_dl.utils.unsmuggle_url(entry["url"])
        entry["id"] = hashlib.sha256(plain_url.encode()).hexdigest()
        return ydl._make_archive_id(entry)
    return archive_id


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

    async def get_unprocessed_entries(self, playlist: Playlist) -> Iterable[Tuple[str, Any]]:
        ydl_opts = self.ydl_opts.copy()
        ydl_opts["playlistend"] = None if playlist.reverse else self.max_items

        result = []
        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            logger.info("Checking playlist '%s'...", playlist.name)
            try:
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, partial(ydl.extract_info, playlist.url,
                                                                download=False, process=False))
            except youtube_dl.DownloadError as download_error:
                logging.error("Failed to get playlist %s. Error was: '%s'",
                              playlist.name, download_error)
            else:
                entries = info.get("entries", [])
                if playlist.reverse:
                    entries = reversed(list(entries))
                for entry in take(self.max_items, entries):
                    e_hash = make_archive_id(ydl, entry)
                    if e_hash is None:
                        logger.warning("Ignoring malformed playlist entry from %s", playlist.name)
                    else:
                        result.append((e_hash, entry))
        return result

    def _process_ie(self, entry):
        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            processed = ydl.process_ie_result(entry, False)

            # walk through the ie_result dictionary to force evaluation of lazily loaded resources
            repr(processed)

            return processed

    async def process_entry(self, e_hash: str, entry: Any) -> Tuple[str, Optional[Video]]:
        try:
            loop = asyncio.get_event_loop()
            processed = await loop.run_in_executor(None, self._process_ie, entry)
        except youtube_dl.DownloadError as download_error:
            logging.warning("Failed to get a video. Error was: '%s'", download_error)
            return e_hash, None
        else:
            title = processed.get("title")
            if not title:
                logger.error("Failed to process a video, because its title is missing")
                return e_hash, None

            url, _ = youtube_dl.utils.unsmuggle_url(processed.get("webpage_url"))
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

    async def fetch(self, playlist: Playlist) -> List[Video]:
        unprocessed = await self.get_unprocessed_entries(playlist)
        processed = await asyncio.gather(*itertools.starmap(self.process_entry, unprocessed))
        return [v for _, v in processed if v]


class Updater:
    def __init__(self, db_path: str, max_backlog=20, max_fail=5):
        self.db_path = db_path
        self.max_items = max_backlog
        self.max_fail = max_fail
        self.fetcher = Fetcher(max_backlog)
        self.database = Database(self.db_path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.database.__exit__(exc_type, exc_val, exc_tb)

    async def get_new_entries(self, playlist: Playlist) -> Iterable[Tuple[Any, str]]:
        hashes = frozenset(
            x.extractor_hash
            for x in self.database.list_videos(playlists=[playlist.name])
        )
        items = await self.fetcher.get_unprocessed_entries(playlist)

        return [
            (e_hash, entry)
            for e_hash, entry in items
            if e_hash not in hashes
               and self.database.get_extractor_fail_count(e_hash) < self.max_fail
        ]

    async def update_playlist(self, playlist: Playlist):
        new_entries = await self.get_new_entries(playlist)
        result = await asyncio.gather(*itertools.starmap(self.fetcher.process_entry, new_entries))
        for e_hash, video in result:
            if video is not None:
                self.database.add_videos([video], playlist)
            else:
                self.database.increase_extractor_fail_count(e_hash, max_fail=self.max_fail)

    async def do_update(self):
        playlists = self.database.list_playlists()
        await asyncio.gather(*map(self.update_playlist, playlists))

    def update(self):
        asyncio.run(self.do_update())
