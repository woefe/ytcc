# ytcc - The YouTube channel checker
# Copyright (C) 2025  Wolfgang Popp
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
import asyncio

import pytest

from ytcc.database import Playlist
from ytcc.updater import Fetcher, youtube_dl


class _ExtractorFailingYDL:
    """Stands in for YoutubeDL when an extractor crashes instead of raising DownloadError."""

    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def extract_info(self, *_args, **_kwargs):
        # Mirrors yt-dlp's peertube extractor when the webpage download fails:
        # the response is a bool, and calling .get() on it raises AttributeError.
        info = False
        return info.get("displayName")


@pytest.fixture
def playlist():
    return Playlist(name="failing", url="https://example.invalid/playlist", reverse=False)


def test_playlist_fetch_survives_extractor_crash(monkeypatch, playlist):
    monkeypatch.setattr(youtube_dl, "YoutubeDL", _ExtractorFailingYDL)

    fetcher = Fetcher(max_backlog=20)
    entries = asyncio.run(fetcher.get_unprocessed_entries(playlist))

    assert entries == []
