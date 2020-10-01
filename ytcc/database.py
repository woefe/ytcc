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

import logging
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Iterable, Any, Optional, Dict, overload, Tuple

from ytcc import config
from ytcc.config import Direction, VideoAttr
from ytcc.exceptions import IncompatibleDatabaseVersion, PlaylistDoesNotExistException
from ytcc.utils import unpack_optional

logger = logging.getLogger(__name__)


def logging_cb(querystr: str) -> None:
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("%s", " ".join(querystr.split()))


def _placeholder(elements: List[Any]) -> str:
    return ",".join("?" * len(elements))


@dataclass(frozen=True)
class Playlist:
    name: str
    url: str


@dataclass(frozen=True)
class Video:
    url: str
    title: str
    description: str
    publish_date: float
    watched: bool
    duration: float
    extractor_hash: str


@dataclass(frozen=True)
class MappedVideo(Video):
    id: int
    playlists: List[Playlist]


@dataclass(frozen=True)
class MappedPlaylist(Playlist):
    tags: List[str]


class Database:
    VERSION = 2

    def __init__(self, path: str = ":memory:"):
        is_new_db = True
        if path != ":memory:":
            expanded_path = Path(path).expanduser()
            expanded_path.parent.mkdir(parents=True, exist_ok=True)
            is_new_db = not expanded_path.is_file()
            path = str(expanded_path)

        sqlite3.register_converter("integer", int)
        sqlite3.register_converter("float", float)
        self.connection = sqlite3.connect(f"{path}", detect_types=sqlite3.PARSE_DECLTYPES)
        self.connection.set_trace_callback(logging_cb)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON;")

        if is_new_db:
            self._populate()

        if int(self.connection.execute("PRAGMA USER_VERSION;").fetchone()[0]) < 2:
            raise IncompatibleDatabaseVersion("Database Schema 2 or higher is required")

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        self.close()

    def _populate(self):
        script = f"""CREATE TABLE tag
            (
                name     VARCHAR NOT NULL,
                playlist INTEGER REFERENCES playlist (id) ON DELETE CASCADE,

                CONSTRAINT tagKey PRIMARY KEY (name, playlist)
            );

            CREATE TABLE playlist
            (
                id   INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                name VARCHAR UNIQUE,
                url  VARCHAR UNIQUE
            );

            CREATE TABLE content
            (
                playlist_id INTEGER NOT NULL REFERENCES playlist (id) ON DELETE CASCADE,
                video_id    INTEGER NOT NULL REFERENCES video (id) ON DELETE CASCADE,

                CONSTRAINT contentKey PRIMARY KEY (playlist_id, video_id)
            );

            CREATE TABLE video
            (
                id             INTEGER        NOT NULL PRIMARY KEY AUTOINCREMENT,
                title          VARCHAR        NOT NULL,
                url            VARCHAR UNIQUE NOT NULL,
                description    VARCHAR,
                duration       FLOAT,
                publish_date   FLOAT,
                watched        INTEGER CONSTRAINT watchedBool CHECK (watched = 1 OR watched = 0),
                extractor_hash VARCHAR UNIQUE
            );

            CREATE TABLE extractor_meta
            (
                extractor_hash VARCHAR PRIMARY KEY,
                failure_count INTEGER
            );

            PRAGMA USER_VERSION = {self.VERSION};
            """
        self.connection.executescript(script)

    def get_extractor_fail_count(self, e_hash) -> int:
        query = "SELECT failure_count FROM extractor_meta WHERE extractor_hash = ?"
        count = self.connection.execute(query, (e_hash,)).fetchone()
        if count is None:
            return 0
        return int(count[0])

    def increase_extractor_fail_count(self, e_hash, max_fail=(1 << 63) - 1) -> None:
        query = """
        INSERT INTO extractor_meta VALUES (:e_hash,1)
            ON CONFLICT (extractor_hash) DO UPDATE
                SET failure_count = failure_count + 1
                WHERE failure_count < :max_fail
        """
        self.connection.execute(query, {"e_hash": e_hash, "max_fail": max_fail})

    def close(self) -> None:
        self.connection.commit()
        self.connection.close()

    def add_playlist(self, name: str, url: str) -> None:
        query = "INSERT INTO playlist (name, url) VALUES (?, ?);"
        self.connection.execute(query, (name, url))

    def delete_playlist(self, name: str) -> bool:
        query = "DELETE FROM playlist WHERE name = ?"
        res = self.connection.execute(query, (name,))
        return res.rowcount > 0

    def rename_playlist(self, oldname, newname) -> bool:
        query = "UPDATE playlist SET name = ? WHERE name = ?"
        try:
            res = self.connection.execute(query, (newname, oldname))
        except sqlite3.IntegrityError:
            return False

        return res.rowcount > 0

    def list_playlists(self) -> Iterable[MappedPlaylist]:
        query = """
        SELECT p.id AS id, p.name AS name, p.url AS url, t.name AS tag
        FROM playlist AS p
            LEFT OUTER JOIN tag AS t ON p.id = t.playlist;
        """
        playlists: Dict[int, MappedPlaylist] = dict()
        for row in self.connection.execute(query):
            playlist = playlists.get(row["id"])
            if playlist is None:
                tags = [row["tag"]] if row["tag"] else []
                playlists[row["id"]] = MappedPlaylist(row["name"], row["url"], tags)
            else:
                playlists[row["id"]].tags.append(row["tag"])

        return playlists.values()

    def tag_playlist(self, playlist: str, tags: List[str]) -> None:
        query_pid = "SELECT id FROM playlist WHERE name = ?"
        query_clear = """DELETE FROM tag WHERE playlist = ?"""
        query_insert = """INSERT OR IGNORE INTO tag (name, playlist) VALUES (?, ?)"""
        with self.connection as con:
            pid = int(con.execute(query_pid, (playlist,)).fetchone()["id"])
            con.execute(query_clear, (pid,))
            con.executemany(query_insert, ((tag, pid) for tag in tags))

    def add_videos(self, videos: Iterable[Video], playlist: Playlist) -> None:
        insert_video = """
            INSERT INTO video
                (title, url, description, duration, publish_date, watched, extractor_hash)
            VALUES
                (:title, :url, :description, :duration, :publish_date, :watched, :extractor_hash)
            ON CONFLICT (url) DO UPDATE
                SET title = :title,
                    url = :url,
                    description = :description,
                    duration = :duration,
                    publish_date = :publish_date,
                    extractor_hash = :extractor_hash
            """
        insert_playlist = """
            INSERT OR IGNORE INTO content (playlist_id, video_id)
            VALUES (?,(SELECT id FROM video WHERE url = ?));
            """
        with self.connection as con:
            cursor = con.execute("SELECT id FROM playlist WHERE name = ?", (playlist.name,))
            fetch = cursor.fetchone()
            if fetch is None:
                raise PlaylistDoesNotExistException(
                    f"Playlist \"{playlist.name}\" is not in the database."
                )
            playlist_id = fetch["id"]
            for video in videos:
                cursor.execute(insert_video, asdict(video))
                cursor.execute(insert_playlist, (playlist_id, video.url))

    @overload
    def mark_watched(self, video: List[int]) -> None:
        ...

    @overload
    def mark_watched(self, video: int) -> None:
        ...

    @overload
    def mark_watched(self, video: MappedVideo) -> None:
        ...

    def mark_watched(self, video: Any) -> None:
        if isinstance(video, int):
            videos = [video]
        elif isinstance(video, list):
            videos = video
        elif isinstance(video, MappedVideo):
            videos = [video.id]
        else:
            raise TypeError(f"Cannot mark object of type {type(video)} as watched.")

        query = "UPDATE video SET watched = 1 WHERE id = ?"
        with self.connection as con:
            con.executemany(query, ((int(video),) for video in videos))

    def list_videos(self,
                    since: Optional[float] = None,
                    till: Optional[float] = None,
                    watched: Optional[bool] = None,
                    tags: Optional[List[str]] = None,
                    playlists: Optional[List[str]] = None,
                    ids: Optional[List[int]] = None) -> Iterable[MappedVideo]:

        tag_condition = f"AND t.name IN ({_placeholder(tags)})" if tags is not None else ""
        id_condition = f"AND v.id IN ({_placeholder(ids)})" if ids is not None else ""

        playlist_condition = ""
        if playlists is not None:
            playlist_condition = f"AND p.name IN ({_placeholder(playlists)})"

        watched_condition = {
            None: "",
            True: "AND v.watched",
            False: "AND not v.watched"
        }.get(watched, "")

        order_by_clause = ""
        if config.ytcc.order_by:
            def directions() -> Iterable[Tuple[str, str]]:
                column_names = {
                    VideoAttr.ID: "id",
                    VideoAttr.URL: "url",
                    VideoAttr.TITLE: "title",
                    VideoAttr.DESCRIPTION: "description",
                    VideoAttr.PUBLISH_DATE: "publish_date",
                    VideoAttr.WATCHED: "watched",
                    VideoAttr.DURATION: "duration",
                    VideoAttr.EXTRACTOR_HASH: "extractor_hash",
                    VideoAttr.PLAYLISTS: "playlist_name",
                }
                for untrusted_col, untrusted_dir in config.ytcc.order_by:
                    ord_dir = 'ASC' if untrusted_dir == Direction.ASC else 'DESC'
                    col = column_names.get(untrusted_col)
                    if col is not None:
                        yield col, ord_dir

            order_by_clause = "ORDER BY "
            order_by_clause += ", ".join(f"{col} {ord_dir}" for col, ord_dir in directions())

        query = f"""
            SELECT v.id             AS id,
                   v.title          AS title,
                   v.url            AS url,
                   v.description    AS description,
                   v.duration       AS duration,
                   v.publish_date   AS publish_date,
                   v.watched        AS watched,
                   v.extractor_hash AS extractor_hash,
                   p.name           AS playlist_name,
                   p.url            AS playlist_url
            FROM video AS v
                     JOIN content c ON v.id = c.video_id
                     JOIN playlist p ON p.id = c.playlist_id
                     LEFT JOIN tag AS t ON p.id = t.playlist
            WHERE
                v.publish_date > ?
                AND v.publish_date < ?
                {watched_condition}
                {tag_condition}
                {id_condition}
                {playlist_condition}
            {order_by_clause}
            """
        since = unpack_optional(since, lambda: 0)
        till = unpack_optional(till, lambda: float("inf"))
        playlists = unpack_optional(playlists, list)
        tags = unpack_optional(tags, list)
        ids = unpack_optional(ids, list)

        videos: Dict[int, MappedVideo] = dict()
        with self.connection as con:
            for row in con.execute(query, [since, till, *ids, *tags, *playlists]):
                video = videos.get(row["id"])
                if video is None:
                    videos[row["id"]] = MappedVideo(
                        id=row["id"],
                        url=row["url"],
                        title=row["title"],
                        description=row["description"],
                        publish_date=row["publish_date"],
                        watched=row["watched"],
                        duration=row["duration"],
                        extractor_hash=row["extractor_hash"],
                        playlists=[Playlist(row["playlist_name"], row["playlist_url"])]
                    )
                else:
                    videos[row["id"]].playlists.append(
                        Playlist(row["playlist_name"], row["playlist_url"])
                    )

        return videos.values()

    def cleanup(self) -> None:
        """Delete all watched videos."""
        sql = """
            DELETE
            FROM video
            WHERE watched = 1;
            """
        with self.connection as con:
            con.execute(sql)
        self.connection.execute("VACUUM;")
