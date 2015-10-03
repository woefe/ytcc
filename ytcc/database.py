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
import os.path
import time

class Database:
    """Database interface for ytcc"""

    def __init__(self, path):
        isNewDB = not os.path.exists(path)
        self.dbconn = sqlite3.connect(path)
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
                displayname varchar,
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

    def _make_place_holder(self, size):
        return "(" + ("?," * (size - 1)) + "?)"

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

        Returns ([(int, str)]):
            A list of tuples of the form (id, name).
        """

        sqlstatement = "select id, displayname from channel;"
        return self._execute_query_with_result(sqlstatement)

    def list_channel_yt_ids(self):
        """Returns a list of the id on youtube of every channel.

        Returns (list of string):
            A list containing the youtube ids of all channels.
        """

        sqlstatement = "select yt_channelid from channel;"
        queryResult = self._execute_query_with_result(sqlstatement)
        return [x[0] for x in queryResult]

    def get_yt_video_id(self, videoId):
        """Returns the videoId on youtube for a given (internal) videoId.

        Returns (str):
            The youtube videoId.
        """

        sqlstatement = "select yt_videoid from video where id = ?;"
        queryResult = self._execute_query_with_result(sqlstatement, (videoId,))
        return queryResult[0][0]

    def list_unwatched_videos_with_filter(self, channelFilter):
        """Returns a list of unwatched videos. The videos are published by the
        channels in channelFilter.

        Args:
            channelFilter (list): the list of channelIds

        Returns (list):
            A list of tuples of the form (vID, title, description, publish_date, channel)
        """

        sqlstatement = """
            select v.id, v.title, v.description, v.publish_date, c.displayname
            from video v, channel c
            where v.watched = 0
                and v.publisher = c.yt_channelid
                and c.id in """ + self._make_place_holder(len(channelFilter)) + """
            order by c.id, v.publish_date asc;
            """
        return self._execute_query_with_result(sqlstatement, tuple(channelFilter))

    def list_unwatched_videos(self):
        """Returns a list of unwatched videos.

        Returns (list):
            A list of tuples of the form (vID, title, description, publish_date, channel).
        """

        sqlstatement = """
            select v.id, v.title, v.description, v.publish_date, c.displayname
            from video v, channel c
            where v.watched = 0 and v.publisher = c.yt_channelid
            order by c.id, v.publish_date asc;
            """
        return self._execute_query_with_result(sqlstatement)

    def list_recent_videos_with_filter(self, channelFilter):
        """Returns a list of videos that were added within the last week. The
        videos are published by the channels in channelFilter.

        Args:
            channelFilter (list): the list of channelIds

        Returns (list):
            A list of tuples of the form (vID, title, description, publish_date, channel)
        """

        sqlstatement_with_filter = """
            select v.id, v.title, v.description, v.publish_date, c.displayname
            from video v, channel c
            where v.publish_date > strftime("%s") - 604800
                and v.publisher = c.yt_channelid
                and c.id in """ + self._make_place_holder(len(channelFilter)) + """
            order by c.id, v.publish_date asc;
            """
        return self._execute_query_with_result(sqlstatement_with_filter, tuple(channelFilter))

    def list_recent_videos(self):
        """Returns a list of videos that were added within the last week.

        Returns (list):
            A list of tuples of the form (vID, title, description, publish_date, channel)
        """

        sqlstatement = """
            select v.id, v.title, v.description, v.publish_date, c.displayname
            from video v, channel c
            where v.publish_date > strftime("%s") - 604800
                and v.publisher = c.yt_channelid
            order by c.id, v.publish_date asc;
            """
        return self._execute_query_with_result(sqlstatement)

    def mark_watched(self, channelFilter):
        sqlstatement = """
            update video
            set watched = 1
            where watched = 0
                and publisher in (
                    select yt_channelid
                    from channel
                    where id in """ + self._make_place_holder(len(channelFilter)) + """)
            """
        self._execute_query(sqlstatement, tuple(channelFilter))


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

    def video_watched(self, vID):
        """Mark a video as watched.

        Args:
            vID (int): The video's ID.
        """

        sqlstatement = "update video set watched = 1 where id = ?"
        self._execute_query(sqlstatement, (vID,))

    def delete_channel(self, cID):
        """Delete (or unsubscribe) a channel.

        Args:
            cID (int): The channel's ID.
        """

        sqlstatement = "delete from channel where id = ?"
        self._execute_query(sqlstatement, (cID,))

    def add_videos(self, videos):
        """Adds new videos to the database.

        Args:
            videos (list): The list of videos to add. The list contains tuples
                of the form:
                (yt_videoid, title, description, publisher, publish_date, watched).
        """

        sqlstatement = "insert or ignore into video(yt_videoid, title, description, publisher, publish_date, watched) values (?, ?, ?, ?, ?, ?);"
        self._execute_query_many(sqlstatement, videos)

    def get_video_info(self, vID):
        """Returns id, title, description, publish date, channel name for a
        given video id.

        Returns (tuple)
            The tuple containing all the above listed information or None if the
            id does not exist.
        """

        sqlstatement = """
            select v.id, v.title, v.description, v.publish_date, c.displayname
            from video v, channel c
            where v.id = ? and v.publisher = c.yt_channelid
            """
        queryResult = self._execute_query_with_result(sqlstatement, (vID,))
        if queryResult:
            return queryResult[0]
        else:
            return None


