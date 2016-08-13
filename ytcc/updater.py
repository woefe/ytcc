# ytcc - The YouTube channel checker
# Copyright (C) 2016  Wolfgang Popp
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

FROM_0_TO_1 = '''
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

    INSERT INTO user_search (id, channel, title, description)
        SELECT
            v.id,
            c.displayname,
            v.title,
            v.description
        FROM video v
            JOIN channel c ON c.yt_channelid = v.publisher;

    PRAGMA USER_VERSION = 1;
    '''

UPDATES = [FROM_0_TO_1]


def update(old_version, new_version, dbconn):
    """Updates the database from the old_version to the new_version

    Args:
        old_version (int): the old database version
        new_version (int): the new database version
        dbconn (sqlite3.Connection): the connection to the database wich is updated
    """

    print(type(old_version))
    print(type(new_version))
    c = dbconn.cursor()
    for script in UPDATES[old_version:new_version]:
        c.executescript(script)
    dbconn.commit()
    c.close()
