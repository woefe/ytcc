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
        isNewDB = not path.is_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.dbconn = sqlite3.connect(str(path))
        if isNewDB:
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

    def _execute_query(self, sqlstatement, args=()):
        # Helper method to execute sql queries that do not have return values e.g. update, insert,...
        c = self.dbconn.cursor()
        c.execute(sqlstatement, args)
        self.dbconn.commit()
        c.close()

    def _execute_query_with_result(self, sqlstatement, args=()):
        # Helper method to execute sql queries that return values e.g. select,...
        c = self.dbconn.cursor()
        result = c.execute(sqlstatement, args).fetchall()
        self.dbconn.commit()
        c.close()
        return result

    def _execute_query_many(self, sqlstatement, args):
        # Helper method for cursor.executemany()
        c = self.dbconn.cursor()
        c.executemany(sqlstatement, args)
        self.dbconn.commit()
        c.close()

    def _make_place_holder(self, list):
        if list:
            return "(" + ("?," * (len(list) - 1)) + "?)"
        else:
            return "()"

    def add_channel(self, name, yt_channelid):
        """Adds a new channel to the database.

        Args:
            name (str): The channel's (display)name.
            yt_channelid (str): The channel's id on youtube.com"
        """

        sqlInsertChannel = "insert into channel(displayname, yt_channelid) values (?, ?);"
        self._execute_query(sqlInsertChannel, (name, yt_channelid))

    def list_channels(self):
        """Returns a list of all subscribed channels.

        Returns ([str]):
            A list of tuples of the form (id, name).
        """

        sqlstatement = "select * from channel;"
        queryResult = self._execute_query_with_result(sqlstatement)
        return [Channel(*x) for x in queryResult]

    def list_videos(self, channelFilter=None, timestamp=0, includeWatched=True):
        """Returns a list of videos that were published after the given timestamp. The
        videos are published by the channels in channelFilter.

        Args:
            channelFilter (list): the list of channel names
            timestamp (int): timestamp in seconds
            includeWatched (bool): true, if watched videos should be included in the result

        Returns (list):
            A list of tuples of the form (vID, title, description, publish_date, channel)
        """

        sqlstatement = """
            select v.id, v.yt_videoid, v.title, v.description, v.publish_date, c.displayname
            from video v, channel c
            where v.publisher = c.yt_channelid
                and v.publish_date > @timestamp
                and (@include_watched or v.watched = 0)
                and (@all_channels or c.displayname in """ + self._make_place_holder(channelFilter) + """)
            order by c.id, v.publish_date asc;
            """

        sqlargs = channelFilter.copy() if channelFilter is not None else []
        sqlargs.insert(0, timestamp)
        sqlargs.insert(1, includeWatched)
        sqlargs.insert(2, channelFilter is None)
        queryResult = self._execute_query_with_result(sqlstatement, tuple(sqlargs))
        return [Video(*x) for x in queryResult]

    def get_video(self, vID):
        """Returns id, title, description, publish date, channel name for a
        given video id.

        Returns (tuple)
            The tuple containing all the above listed information or None if the
            id does not exist.
        """

        sqlstatement = """
            select v.id, v.yt_videoid, v.title, v.description, v.publish_date, c.displayname
            from video v, channel c
            where v.id = ? and v.publisher = c.yt_channelid
            """
        queryResult = self._execute_query_with_result(sqlstatement, (vID,))
        if queryResult:
            return Video(*queryResult[0])
        else:
            return None

    def mark_watched(self, channelFilter, timestamp=0):
        """Marks all videos that are older than the given timestamp and are published by
        channels in the given filter as watched.

        Args:
            channelFilter (list): the list of channel names
            timestamp (int): timestamp in seconds
        """

        sqlstatement = """
            update video
            set watched = 1
            where watched = 0
                publish_date < @timestamp
                and publisher in (
                    select yt_channelid
                    from channel
                    where displayname in """ + self._make_place_holder(channelFilter) + """)
            """

        sqlargs = channelFilter.copy() if channelFilter is not None else []
        sqlargs.insert(0, timestamp)
        self._execute_query(sqlstatement, tuple(sqlargs))

    def mark_all_watched(self):
        """Marks all unwatched videos as watched without playing them."""

        sqlstatement = "update video set watched = 1 where watched = 0"
        self._execute_query(sqlstatement)

    def mark_some_watched(self, vIDs):
        """Marks the videos identified by vIDs as watched without playing them.

        Args:
            vIDs (list of int): The video IDs to mark as watched.
        """

        sqlstatement = "update video set watched = 1 where id = ?"
        self._execute_query_many(sqlstatement, [(id,) for id in vIDs])

    def delete_channel(self, displayname):
        """Delete (or unsubscribe) a channel.

        Args:
            cID (str): The channel's displayname.
        """

        sqlstatement = "delete from channel where displayname = ?"
        self._execute_query(sqlstatement, (displayname,))

    def add_videos(self, videos):
        """Adds new videos to the database.

        Args:
            videos (list): The list of videos to add. The list contains tuples
                of the form:
                (yt_videoid, title, description, publisher, publish_date, watched).
        """

        sqlstatement = "insert or ignore into video(yt_videoid, title, description, publisher, publish_date, watched) values (?, ?, ?, ?, ?, ?);"
        self._execute_query_many(sqlstatement, videos)

