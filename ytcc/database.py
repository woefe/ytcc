# ytcc - The YouTube channel checker
# Copyright (C) 2017  Wolfgang Popp
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
import ytcc.updater as updater
from ytcc.video import Video
from ytcc.channel import Channel


class Database:
    """Database interface for ytcc"""

    VERSION = 1

    def __init__(self, path):
        """Connects to the given sqlite3 database file or creates a new file,
        if it does not yet exist.

        Args:
            path (pathlib.Path): the path to the sqlite database file
        """

        path = path.expanduser()
        is_new_db = not path.is_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.dbconn = sqlite3.connect(str(path))
        if is_new_db:
            self._init_db()
        else:
            self._maybe_update()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dbconn.close()

    def _init_db(self):
        """Creates all needed tables."""

        c = self.dbconn.cursor()
        c.executescript('''
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
                publisher    VARCHAR REFERENCES channel (yt_channelid),
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

            PRAGMA USER_VERSION = ''' + str(Database.VERSION) + ";")
        self.dbconn.commit()
        c.close()

    def _maybe_update(self):
        db_version = int(self._execute_query_with_result("PRAGMA USER_VERSION;")[0][0])
        if db_version < Database.VERSION:
            updater.update(db_version, Database.VERSION, self.dbconn)

    def _execute_query(self, sql, args=()):
        # Helper method to execute sql queries that do not have return values e.g. update, insert,...
        c = self.dbconn.cursor()
        c.execute(sql, args)
        self.dbconn.commit()
        c.close()

    def _execute_query_with_result(self, sql, args=()):
        # Helper method to execute sql queries that return values e.g. select,...
        c = self.dbconn.cursor()
        result = c.execute(sql, args).fetchall()
        self.dbconn.commit()
        c.close()
        return result

    def _execute_query_many(self, sql, args):
        # Helper method for cursor.executemany()
        c = self.dbconn.cursor()
        c.executemany(sql, args)
        self.dbconn.commit()
        c.close()

    @staticmethod
    def _make_place_holder(elements):
        if elements:
            return "(" + ("?," * (len(elements) - 1)) + "?)"
        else:
            return "()"

    def add_channel(self, name, yt_channelid):
        """Adds a new channel to the database.

        Args:
            name (str): The channel's (display)name.
            yt_channelid (str): The channel's id on youtube.com"
        """

        sql = "insert into channel(displayname, yt_channelid) values (?, ?);"
        self._execute_query(sql, (name, yt_channelid))

    def list_channels(self):
        """Returns a list of all subscribed channels.

        Returns ([str]):
            A list of tuples of the form (id, name).
        """

        sql = "select * from channel;"
        result = self._execute_query_with_result(sql)
        return [Channel(*x) for x in result]

    def list_videos(self, channel_filter=None, begin_timestamp=0, end_timestamp=0, include_watched=True):
        """Returns a list of videos that were published after the given timestamp. The
        videos are published by the channels in channelFilter.

        Args:
            channel_filter (list): the list of channel names
            begin_timestamp (int): timestamp in seconds
            end_timestamp (int): timestamp in seconds
            include_watched (bool): true, if watched videos should be included in the result

        Returns (list):
            A list of ytcc.video.Video
        """

        sql = """
            select v.id, v.yt_videoid, v.title, v.description, v.publish_date, c.displayname
            from video v, channel c
            where v.publisher = c.yt_channelid
                and v.publish_date > @begin_timestamp
                and v.publish_date < @end_timestamp
                and (@include_watched or v.watched = 0)
                and (@all_channels or c.displayname in """ + \
                        self._make_place_holder(channel_filter) + """)
            order by c.id, v.publish_date asc;
            """

        sql_args = channel_filter.copy() if channel_filter is not None else []
        sql_args.insert(0, begin_timestamp)
        sql_args.insert(1, end_timestamp)
        sql_args.insert(2, include_watched)
        sql_args.insert(3, channel_filter is None or len(channel_filter) < 1)
        result = self._execute_query_with_result(sql, tuple(sql_args))
        return [Video(*x) for x in result]

    def search(self, searchterm):
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
                c.displayname
            FROM video v
                JOIN channel c ON v.publisher = c.yt_channelid
                JOIN user_search s ON v.id = s.id
            WHERE s.user_search MATCH ?;
            """

        result = self._execute_query_with_result(sql, (searchterm,))
        return [Video(*x) for x in result]

    def get_video(self, video_id):
        """Queries and returns the video object for the given video ID.

        Args:
            video_id (int): the video ID.

        Returns (ytcc.video.Video)
            The video identified by the given video ID.
        """

        sql = """
            select v.id, v.yt_videoid, v.title, v.description, v.publish_date, c.displayname
            from video v, channel c
            where v.id = ? and v.publisher = c.yt_channelid
            """
        result = self._execute_query_with_result(sql, (video_id,))
        if result:
            return Video(*result[0])

        return None

    def mark_some_watched(self, video_ids):
        """Marks the videos identified by the given video IDs as watched without playing them.

        Args:
            video_ids (list of int): The video IDs to mark as watched.
        """

        sql = "update video set watched = 1 where id = ?"
        self._execute_query_many(sql, [(vid,) for vid in video_ids])

    def delete_channels(self, displaynames):
        """Delete (or unsubscribe) channels.

        Args:
            displaynames (list): A list of channels' displaynames.
        """

        sql = "delete from channel where displayname in " + self._make_place_holder(displaynames) \
                + ";"
        self._execute_query(sql, tuple(displaynames))

    def add_videos(self, videos):
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

    def cleanup(self):
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
        self._execute_query_many(sql, [(e.displayname,) for e in self.list_channels()])
        self._execute_query("vacuum;")
