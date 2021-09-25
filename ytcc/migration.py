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

import sqlite3
from datetime import datetime

V3_WATCH_DATE = f"""
CREATE TABLE new_video
(
    id             INTEGER        NOT NULL PRIMARY KEY AUTOINCREMENT,
    title          VARCHAR        NOT NULL,
    url            VARCHAR UNIQUE NOT NULL,
    description    VARCHAR,
    duration       FLOAT,
    publish_date   FLOAT,
    watch_date     FLOAT,
    extractor_hash VARCHAR UNIQUE
);

INSERT INTO new_video
SELECT id,
       title,
       url,
       description,
       duration,
       publish_date,
       NULL,
       extractor_hash
FROM video
WHERE watched = 0;

INSERT INTO new_video
SELECT id,
       title,
       url,
       description,
       duration,
       publish_date,
       {datetime.now().timestamp()},
       extractor_hash
FROM video
WHERE watched = 1;

DROP TABLE video;

ALTER TABLE new_video
    RENAME TO video;

PRAGMA foreign_key_check;
"""

V4_PLAYLIST_REVERSE = """
ALTER TABLE playlist ADD COLUMN reverse BOOLEAN;

UPDATE playlist SET reverse = false WHERE reverse IS NULL;
"""

V5_VIDEO_THUMBNAIL_URL = """
ALTER TABLE video ADD COLUMN thumbnail_URL VARCHAR;
"""

UPDATES = ["-- noop", "-- noop", V3_WATCH_DATE, V4_PLAYLIST_REVERSE, V5_VIDEO_THUMBNAIL_URL]


def migrate(old_version: int, new_version: int, db_conn: sqlite3.Connection) -> None:
    if new_version <= old_version:
        return

    db_conn.execute("PRAGMA foreign_keys = OFF")
    with db_conn as conn:
        for script in UPDATES[old_version:new_version]:
            conn.executescript(script)
        conn.execute(f"PRAGMA user_version = {new_version}")

    db_conn.execute("PRAGMA foreign_keys = ON")
