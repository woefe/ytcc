# ytcc - The YouTube channel checker
# Copyright (C) 2019  Wolfgang Popp
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
import subprocess
import json

from typing import TypeVar, Optional, Callable
import youtube_dl

# pylint: disable=invalid-name
T = TypeVar("T")


def unpack_optional(elem: Optional[T], default: Callable[[], T]) -> T:
    if elem is None:
        return default()
    return elem


def list_playlist(playlist_url: str):
    with youtube_dl.YoutubeDL({"extract_flat": True, "playlistend": 10, "quiet": True}) as ydl:
        playlist_info = ydl.extract_info(playlist_url, download=False)

    videos = []
    assert playlist_info["_type"] == "playlist"
    playlist_title = playlist_info["title"]

    for entry in playlist_info["entries"]:
        videos.append({
            "url": entry["url"],
            "title": entry["title"]
        })

    return videos, playlist_title


def get_video_information(video_url:str):
    with youtube_dl.YoutubeDL({"quiet": True}) as ydl:
        output = ydl.extract_info(video_url, download=False)
    return output
