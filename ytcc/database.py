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
from pathlib import Path
import ytcc.updater as updater
from ytcc.video import Video
from ytcc.channel import Channel
from typing import Tuple, Any, List, Iterable, Optional

DBVideo = Tuple[str, str, str, str, float, bool]


class Database:
    """Database interface for ytcc"""

    VERSION = 1

    def __init__(self, path: str = ":memory:") -> None:
        """Connects to the given sqlite3 database file or creates a new file, if it does not yet
        exist. If 'path' is not given, a new database is created in memory.

        Args:
            path (str): the path to the sqlite database file
        """

        is_new_db = True
        if path != ":memory:":
            p = Path(path).expanduser()
            is_new_db = not p.is_file()
            p.parent.mkdir(parents=True, exist_ok=True)
            path = str(p)

        self.dbconn = sqlite3.connect(path)
        # TODO Enable foreign key support on next major release
        # self._execute_query("PRAGMA foreign_keys = ON;")
        if is_new_db:
            self._init_db()
        else:
            self._maybe_update()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        self.dbconn.close()

    def _init_db(self) -> None:
        """Creates all needed tables."""

        cursor = self.dbconn.cursor()
        cursor.executescript(f"""
            CREATE TABLE channel (
                id           INTEGER NOT NULL PRIMARY KEY,
                displayname  VARCHAR UNIQUE,
                yt_channelid VARCHAR UNIQUE
            );

            CREATE TABLE video (
                id           INTEGER NOT NULL PRIMARY KEY,
                yt_videoid   VARCHAR UNIQUE,
                title        VARCHAR,
                description  VARCHAR,
                publisher    VARCHAR REFERENCES channel (yt_channelid) ON DELETE CASCADE,
                publish_date FLOAT,
                watched      INTEGER CONSTRAINT watchedBool CHECK (watched = 1 OR watched = 0)
            );

            CREATE VIRTUAL TABLE user_search USING fts4(id, channel, title, description, tokenize = unicode61);

            CREATE TRIGGER IF NOT EXISTS populate_search
            AFTER INSERT ON video FOR EACH ROW
            BEGIN
                INSERT INTO user_search (id, channel, title, description)
                    SELECT
                        v.id,
                        c.displayname,
                        v.title,
                        v.description
                    FROM video v
                        JOIN channel c ON v.publisher = c.yt_channelid
                    WHERE v.id = NEW.id;
            END;

            CREATE TRIGGER IF NOT EXISTS delete_from_search
            AFTER DELETE ON video FOR EACH ROW
            BEGIN
                DELETE FROM user_search WHERE id = OLD.id;
            END;

            PRAGMA USER_VERSION = {Database.VERSION};""")
        self.dbconn.commit()
        cursor.close()

    def _maybe_update(self) -> None:
        db_version = int(self._execute_query_with_result("PRAGMA USER_VERSION;")[0][0])
        if db_version < Database.VERSION:
            updater.update(db_version, Database.VERSION, self.dbconn)

    def _execute_query(self, sql: str, args: Tuple = ()) -> None:
        # Helper method to execute sql queries that do not have return values e.g. update, insert
        cursor = self.dbconn.cursor()
        cursor.execute(sql, args)
        self.dbconn.commit()
        cursor.close()

    def _execute_query_with_result(self, sql: str, args: Tuple = ()) -> List[Tuple]:
        # Helper method to execute sql queries that return values e.g. select,...
        cursor = self.dbconn.cursor()
        result = cursor.execute(sql, args).fetchall()
        self.dbconn.commit()
        cursor.close()
        return result

    def _execute_query_many(self, sql: str, args: Iterable[Iterable[Any]]) -> None:
        # Helper method for cursor.executemany()
        cursor = self.dbconn.cursor()
        cursor.executemany(sql, args)
        self.dbconn.commit()
        cursor.close()

    @staticmethod
    def _make_place_holder(elements: Optional[List[Any]] = None) -> str:
        if elements:
            return "(" + ("?," * (len(elements) - 1)) + "?)"
        return "()"

    def add_channel(self, name: str, yt_channelid: str) -> None:
        """Adds a new channel to the database.

        Args:
            name (str): The channel's (display)name.
            yt_channelid (str): The channel's id on youtube.com"
        """

        sql = "insert into channel(displayname, yt_channelid) values (?, ?);"
        self._execute_query(sql, (name, yt_channelid))

    def get_channels(self) -> List[Channel]:
        """Returns a list of all subscribed channels.

        Returns ([Channel]):
            A list of Channel objects.
        """

        sql = "select * from channel;"
        result = self._execute_query_with_result(sql)
        return [Channel(*x) for x in result]

    def get_videos(self, channel_filter: Optional[List[str]] = None, begin_timestamp: float = 0,
                   end_timestamp: float = 0, include_watched: bool = True, 
                   orderby: Optional[List[str]]=None) -> List[Video]:
        """Returns a list of videos that were published after and before the given timestamps. The
        videos are published by the channels in channelFilter.

        Args:
            channel_filter (list): the list of channel names. None or [] match all channels.
            begin_timestamp (int): timestamp in seconds
            end_timestamp (int): timestamp in seconds
            include_watched (bool): true, if watched videos should be included in the result
            orderby (list): the list of parameters by which to sort the results, highest priority first

        Returns (list):
            A list of ytcc.video.Video
        """
        
        # Convert options from config file to the strings used in the database.
        config_to_query_param : Dict[str, str] = {
                "id"          : "v.id",
                "title"       : "v.title",
                "description" : "v.description",
                "publish_date": "v.publish_date",
                "watched"     : "v.watched",
                "channel_id"  : "c.id",
                "channel_name": "c.displayname",
            }
        
        # If no argument is passed, use a default.
        sort_params : str = "c.id, v.publish_date"
        if orderby:
            sort_list : List[str] = list()
            for col in orderby:
                # Take care of extra whitespace
                col=col.strip()
                if not col in config_to_query_param.keys():
                    print(_("Ignoring unknown orderBy option: {col}").format(col=col))
                else:
                    sort_list.append(config_to_query_param[col])
            sort_params = ", ".join(sort_list)
        
        sql = """
            select
                v.id,
                v.yt_videoid,
                v.title,
                v.description,
                v.publish_date,
                c.displayname,
                v.watched
            from video v, channel c
            where v.publisher = c.yt_channelid
                and v.publish_date > @begin_timestamp
                and v.publish_date < @end_timestamp
                and (@include_watched or v.watched = 0)
                and (@all_channels or c.displayname in """ + \
              self._make_place_holder(channel_filter) + f""")
            order by {sort_params} asc;
            """

        channel_names = channel_filter.copy() if channel_filter is not None else []
        sql_args = (
            begin_timestamp,
            end_timestamp,
            include_watched,
            channel_filter is None or len(channel_filter) < 1,
            *channel_names
        )
        result = self._execute_query_with_result(sql, sql_args)
        return [Video(*x) for x in result]

    def search(self, searchterm: str) -> List[Video]:
        """Performs a full-text search.

        Returns(list):
            A list of ytcc.video.Video
        """

        sql = """
            SELECT
                v.id,
                v.yt_videoid,
                v.title,
                v.description,
                v.publish_date,
                c.displayname,
                v.watched
            FROM video v
                JOIN channel c ON v.publisher = c.yt_channelid
                JOIN user_search s ON v.id = s.id
            WHERE s.user_search MATCH ?;
            """

        result = self._execute_query_with_result(sql, (searchterm,))
        return [Video(*x) for x in result]

    def resolve_video_id(self, video_id: int) -> Optional[Video]:
        """Queries and returns the video object for the given video ID.

        Args:
            video_id (int): the video ID.

        Returns (ytcc.video.Video)
            The video identified by the given video ID.
        """

        sql = """
            select
                v.id,
                v.yt_videoid,
                v.title,
                v.description,
                v.publish_date,
                c.displayname,
                v.watched
            from video v, channel c
            where v.id = ? and v.publisher = c.yt_channelid
            """
        result = self._execute_query_with_result(sql, (video_id,))
        if result:
            return Video(*result[0])

        return None

    def mark_watched(self, video_ids: Iterable[int]) -> None:
        """Marks the videos identified by the given video IDs as watched without playing them.

        Args:
            video_ids (list of int): The video IDs to mark as watched.
        """

        sql = "update video set watched = 1 where id = ?"
        self._execute_query_many(sql, [(vid,) for vid in video_ids])

    def delete_channels(self, displaynames: List[str]) -> None:
        """Delete (or unsubscribe) channels.

        Args:
            displaynames (list): A list of channels' displaynames.
        """

        sql = f"delete from channel where displayname in {self._make_place_holder(displaynames)};"
        self._execute_query(sql, tuple(displaynames))

    def add_videos(self, videos: Iterable[DBVideo]) -> None:
        """Adds new videos to the database.

        Args:
            videos (list): The list of videos to add. The list contains tuples of the form:
                           (yt_videoid, title, description, publisher, publish_date, watched).
        """

        sql = """
            insert or ignore
            into video(yt_videoid, title, description, publisher, publish_date, watched)
            values (?, ?, ?, ?, ?, ?);
            """
        self._execute_query_many(sql, videos)

    def cleanup(self) -> None:
        """Deletes all videos from all channels, but keeps the 30 latest videos of every channel.
        """

        sql = """
            delete from video
            where id in (
                select v.id
                from video v, channel c
                where v.publisher = c.yt_channelid and c.displayname = ?
                    and v.publish_date <= (
                        select v.publish_date
                        from video v, channel chan
                        where v.publisher = chan.yt_channelid and chan.displayname = c.displayname
                        order by v.publish_date desc
                        limit 30,1
                    )
            )
            """
        self._execute_query_many(sql, [(e.displayname,) for e in self.get_channels()])
        # self._execute_query("vacuum;")

        # Workaround for https://bugs.python.org/issue28518
        self.dbconn.isolation_level = None
        self.dbconn.execute('VACUUM')
        self.dbconn.isolation_level = ''  # note that '' is the default value of isolation_level
