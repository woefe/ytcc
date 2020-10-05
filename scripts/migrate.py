#!/usr/bin/env python3

import sqlite3
#  ytcc - The YouTube channel checker
#  Copyright (C) 2020  Wolfgang Popp
#
#  This file is part of ytcc.
#
#  ytcc is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  ytcc is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with ytcc.  If not, see <http://www.gnu.org/licenses/>.
import sys
import textwrap
from pathlib import Path


def error(message: str):
    print("Error:", message)


def usage():
    help_text = f"""\
    Usage: {sys.argv[0]} --olddb PATH --newdb PATH

      Ytcc migration script.

      Migrates the database used in version 1 to compatible database for version 2.

    OPTIONS:
      --help     Show this message and exit.
      --olddb    Path to the old database file.
      --newdb    Path to the new database file.
    """
    print(textwrap.dedent(help_text))


it = iter(sys.argv[1:])
arg = next(it, None)
old_db_arg = None
new_db_arg = None

while arg:
    if arg == "--help":
        usage()
        sys.exit(1)
    elif arg == "--olddb":
        old_db_arg = next(it, None)
    elif arg == "--newdb":
        new_db_arg = next(it, None)
    arg = next(it, None)

if old_db_arg is None or new_db_arg is None:
    error(f"Missing command line option. Try {sys.argv[0]} --help for help.")
    sys.exit(1)

old_db = Path(old_db_arg)
new_db = Path(new_db_arg)

if not old_db.is_file():
    error(f"{old_db} is not a file!")
    sys.exit(1)

if not new_db.parent.is_dir():
    error(f"{new_db.parent} is not a directory!")
    sys.exit(1)

try:
    import ytcc
    import ytcc.config
except ImportError:
    error("Cannot import ytcc! Make sure ytcc version 2.0.0 or later is installed!")
    sys.exit(1)

if not ytcc.__version__.startswith("2"):
    error(f"ytcc version {ytcc.__version__} is installed. Version 2.0.0 or later is required")
    sys.exit(1)

ytcc.config.ytcc.db_path = str(new_db)
core_v2 = ytcc.Ytcc()
con_v1 = sqlite3.connect(old_db)
video_query = """
    SELECT yt_videoid, title, description, publish_date, watched
    FROM video WHERE publisher = ?
    """

for c_name, yt_channelid in con_v1.execute("SELECT displayname, yt_channelid FROM channel"):
    url = f"https://www.youtube.com/channel/{yt_channelid}/videos"
    try:
        core_v2.add_playlist(c_name, url)
    except ytcc.BadURLException:
        print(
            f"Ignoring {c_name}, because it is not supported by "
            "youtube-dl or does not exist any more"
        )
        continue
    except ytcc.NameConflictError:
        print(f"{c_name} is already subscribed.")

    print(f"Adding videos for {c_name}")
    videos = (
        ytcc.Video(
            url=f"https://www.youtube.com/watch?v={yt_videoid}",
            title=title,
            description=description,
            publish_date=float(publish_date),
            watched=bool(int(watched)),
            duration=0,
            extractor_hash=f"youtube {yt_videoid}"
        )
        for yt_videoid, title, description, publish_date, watched
        in con_v1.execute(video_query, (yt_channelid,))
    )
    core_v2.database.add_videos(videos, ytcc.Playlist(c_name, url))
