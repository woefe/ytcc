# ytcc - The YouTube channel checker
# Copyright (C) 2015  Wolfgang Popp
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
from ytcc.video import Video
from ytcc.channel import Channel


class Database:
    """Database interface for ytcc"""

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dbconn.close()

    def _init_db(self):
        """Creates all needed tables."""

        c = self.dbconn.cursor()
        c.executescript('''
            create table channel (
                id integer not null primary key,
                displayname varchar unique,
                yt_channelid varchar unique
            );
            create table video (
                id integer not null primary key,
                yt_videoid varchar unique,
                title varchar,
                description varchar,
                publisher varchar references channel(yt_channelid),
                publish_date float,
                watched integer constraint watchedBool check(watched = 1 or watched = 0)
            );
        ''')
        self.dbconn.commit()
        c.close()

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

    def list_videos(self, channel_filter=None, timestamp=0, include_watched=True):
        """Returns a list of videos that were published after the given timestamp. The
        videos are published by the channels in channelFilter.

        Args:
            channel_filter (list): the list of channel names
            timestamp (int): timestamp in seconds
            include_watched (bool): true, if watched videos should be included in the result

        Returns (list):
            A list of tuples of the form (vID, title, description, publish_date, channel)
        """

        sql = """
            select v.id, v.yt_videoid, v.title, v.description, v.publish_date, c.displayname
            from video v, channel c
            where v.publisher = c.yt_channelid
                and v.publish_date > @timestamp
                and (@include_watched or v.watched = 0)
                and (@all_channels or c.displayname in """ + self._make_place_holder(channel_filter) + """)
            order by c.id, v.publish_date asc;
            """

        sql_args = channel_filter.copy() if channel_filter is not None else []
        sql_args.insert(0, timestamp)
        sql_args.insert(1, include_watched)
        sql_args.insert(2, channel_filter is None)
        result = self._execute_query_with_result(sql, tuple(sql_args))
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
        else:
            return None

    def mark_watched(self, channel_filter, timestamp=0):
        """Marks all videos that are older than the given timestamp and are published by channels in the given filter as
        watched.

        Args:
            channel_filter (list): the list of channel names
            timestamp (int): timestamp in seconds
        """

        sql = """
            update video
            set watched = 1
            where watched = 0
                and publish_date > @timestamp
                and publisher in (
                    select yt_channelid
                    from channel
                    where displayname in """ + self._make_place_holder(channel_filter) + """)
            """

        sql_args = channel_filter.copy() if channel_filter is not None else []
        sql_args.insert(0, timestamp)
        self._execute_query(sql, tuple(sql_args))

    def mark_all_watched(self):
        """Marks all unwatched videos as watched without playing them."""

        sql = "update video set watched = 1 where watched = 0"
        self._execute_query(sql)

    def mark_some_watched(self, video_ids):
        """Marks the videos identified by the given video IDs as watched without playing them.

        Args:
            video_ids (list of int): The video IDs to mark as watched.
        """

        sql = "update video set watched = 1 where id = ?"
        self._execute_query_many(sql, [(vid,) for vid in video_ids])

    def delete_channel(self, displayname):
        """Delete (or unsubscribe) a channel.

        Args:
            displayname (str): The channel's displayname.
        """

        sql = "delete from channel where displayname = ?"
        self._execute_query(sql, (displayname,))

    def add_videos(self, videos):
        """Adds new videos to the database.

        Args:
            videos (list): The list of videos to add. The list contains tuples of the form:
                           (yt_videoid, title, description, publisher, publish_date, watched).
        """

        sql = "insert or ignore into video(yt_videoid, title, description, publisher, publish_date, watched)" \
              " values (?, ?, ?, ?, ?, ?);"
        self._execute_query_many(sql, videos)
