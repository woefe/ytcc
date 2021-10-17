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

import contextlib
from sqlite3 import IntegrityError
from tempfile import NamedTemporaryFile
from typing import Iterator, Callable, Optional, List, Iterable

import pytest

from ytcc import Database, MappedPlaylist, PlaylistDoesNotExistException, Playlist, Video, \
    MappedVideo


@pytest.fixture
def empty_database() -> Callable[..., Database]:
    @contextlib.contextmanager
    def context() -> Iterator[Database]:
        with NamedTemporaryFile() as db_file:
            db_file.close()
            with Database(db_file.name) as db:
                yield db

    return context


@pytest.fixture
def filled_database() -> Callable[..., Database]:
    @contextlib.contextmanager
    def context() -> Iterator[Database]:
        with NamedTemporaryFile() as db_file:
            db_file.close()
            with Database(db_file.name) as db:
                with db.connection as con:
                    con.executescript("""
                        INSERT INTO playlist (id, name, url, reverse)
                        VALUES (1, 'pl1', 'a', false),
                               (2, 'pl2', 'b', false),
                               (3, 'pl3', 'c', true),
                               (4, 'pl4', 'd', false);

                        INSERT INTO tag (playlist, name)
                        VALUES (1, 'tag1'),
                               (1, 'tag2'),
                               (4, 'tag1');

                        INSERT INTO video (id, title, url, description, duration, publish_date, watch_date, extractor_hash, thumbnail_URL)
                        VALUES (1, 'title1', 'url1', 'description', 1.1, 131231.0, NULL, 'ext hash1', NULL),
                               (2, 'title2', 'url2', 'description', 1.2, 131231.0, NULL, 'ext hash2', NULL),
                               (3, 'title', 'url3', 'description', 1.2, 131231.0, 123441.0, 'ext hash3', NULL),
                               (4, 'title', 'url4', 'description', 5.2, 131231.0, 123442.0, 'ext hash4', 'thumbnail_URL');

                        INSERT INTO content (playlist_id, video_id)
                        VALUES (1, 1),
                               (1, 2),
                               (2, 2),
                               (2, 3),
                               (3, 4);
                        """)
                yield db

    return context


MAPPED_PLAYLISTS = {
    "pl1": MappedPlaylist("pl1", "a", False, ["tag1", "tag2"]),
    "pl2": MappedPlaylist("pl2", "b", False, []),
    "pl3": MappedPlaylist("pl3", "c", True, []),
    "pl4": MappedPlaylist("pl4", "d", False, ["tag1"])
}

PLAYLISTS = {
    "pl1": Playlist("pl1", "a", False),
    "pl2": Playlist("pl2", "b", False),
    "pl3": Playlist("pl3", "c", True),
    "pl4": Playlist("pl4", "d", False)
}

VIDEOS = {
    1: MappedVideo(id=1, title='title1', url='url1', description='description',
                   duration=1.1, publish_date=131231.0, watch_date=None,
                   extractor_hash='ext hash1', thumbnail_url=None, playlists=[PLAYLISTS["pl1"]]),
    2: MappedVideo(id=2, title='title2', url='url2', description='description',
                   duration=1.2, publish_date=131231.0, watch_date=None,
                   extractor_hash='ext hash2', thumbnail_url=None,
                   playlists=[PLAYLISTS["pl1"], PLAYLISTS["pl2"]]),
    3: MappedVideo(id=3, title='title', url='url3', description='description',
                   duration=1.2, publish_date=131231.0, watch_date=123441.0,
                   extractor_hash='ext hash3', thumbnail_url=None, playlists=[PLAYLISTS["pl2"]]),
    4: MappedVideo(id=4, title='title', url='url4', description='description',
                   duration=5.2, publish_date=131231.0, watch_date=123442.0,
                   extractor_hash='ext hash4', thumbnail_url='thumbnail_URL',
                   playlists=[PLAYLISTS["pl3"]])
}


def _check_playlist(db, name: str, expected: Optional[MappedPlaylist]):
    for pl in db.list_playlists():
        if pl.name == name:
            assert pl == expected


def test_extractor_fail_count(empty_database):
    e_hash = "test 23442345"
    with empty_database() as db:
        # Get fail count of not yet existing extractor hash
        assert db.get_extractor_fail_count(e_hash) == 0

        # Increase fail count twice
        db.increase_extractor_fail_count(e_hash)
        assert db.get_extractor_fail_count(e_hash) == 1
        db.increase_extractor_fail_count(e_hash)
        assert db.get_extractor_fail_count(e_hash) == 2

        # Increase fail count more than 4 times with max_fail=4
        db.increase_extractor_fail_count(e_hash, max_fail=4)
        db.increase_extractor_fail_count(e_hash, max_fail=4)
        db.increase_extractor_fail_count(e_hash, max_fail=4)
        db.increase_extractor_fail_count(e_hash, max_fail=4)
        db.increase_extractor_fail_count(e_hash, max_fail=4)
        assert db.get_extractor_fail_count(e_hash) == 4

        # Increase with increased max_fail
        db.increase_extractor_fail_count(e_hash, max_fail=5)
        assert db.get_extractor_fail_count(e_hash) == 5

        # Increase with basically unlimited max_fail
        db.increase_extractor_fail_count(e_hash)
        assert db.get_extractor_fail_count(e_hash) == 6


def test_add_playlist(empty_database):
    with empty_database() as db:
        # Successful insert of playlist
        assert db.add_playlist("pl1", "http://asdf.kom", False)

        # Unsuccessful insert with existing URL
        with pytest.raises(IntegrityError):
            db.add_playlist("pl2", "http://asdf.kom", False)

        # Unsuccessful insert with existing Name
        with pytest.raises(IntegrityError):
            db.add_playlist("pl1", "http://anotherasdf.kom", True)

        # Unsuccessful insert with existing Name and URL
        with pytest.raises(IntegrityError):
            db.add_playlist("pl1", "http://asdf.kom", False)


def test_delete_playlist(filled_database):
    with filled_database() as db:
        # Try deleting non-existing list
        assert not db.delete_playlist("non-existing")

        # Delete pl1 twice
        assert db.delete_playlist("pl1")
        assert not db.delete_playlist("pl1")

        # Check if tags used with other lists are still there
        assert set(db.list_tags()) == {"tag1"}

        # Ensure videos of pl1 removed
        assert list(db.list_videos(playlists=["pl1"])) == []

        # Ensure videos on other lists are not removed
        video_ids = [v.id for v in db.list_videos()]
        assert 1 not in video_ids
        assert 2 in video_ids


def test_rename_playlist(filled_database):
    with filled_database() as db:
        # Successful rename
        assert db.rename_playlist("pl1", "plx")
        _check_playlist(db, "plx", MappedPlaylist("plx", "a", False, ["tag1", "tag2"]))

        # Unsuccessful rename of non-existing list
        assert not db.rename_playlist("non-existing", "new-pl")

        # Unsuccessful rename of list to already existing name
        assert not db.rename_playlist("pl2", "pl3")


def test_reverse_playlist(filled_database):
    with filled_database() as db:
        # Reverse once
        assert db.reverse_playlist("pl2")
        _check_playlist(db, "pl2", MappedPlaylist("pl2", "b", True, []))

        # Reverse twice
        assert db.reverse_playlist("pl2")
        _check_playlist(db, "pl2", MappedPlaylist("pl2", "b", False, []))

        # Try to reverse non-existing
        assert not db.reverse_playlist("non-existing")


def test_list_playlist(filled_database):
    pls = MAPPED_PLAYLISTS.copy()
    with filled_database() as db:
        for pl in db.list_playlists():
            assert pls[pl.name] == pl
            del pls[pl.name]

        assert pls == {}


def test_tag_playlist(filled_database):
    with filled_database() as db:
        # Set one tag
        db.tag_playlist("pl1", ["tag1"])
        _check_playlist(db, "pl1", MappedPlaylist("pl1", "a", False, ["tag1"]))

        # Remove tags.
        db.tag_playlist("pl4", [])
        _check_playlist(db, "pl4", MappedPlaylist("pl4", "d", False, []))

        # Add tags again, after removing them before. Second addition does not change anything
        db.tag_playlist("pl4", ["tag1", "tag4"])
        db.tag_playlist("pl4", ["tag1", "tag4"])
        _check_playlist(db, "pl4", MappedPlaylist("pl4", "d", False, ["tag1", "tag4"]))

        # Try tagging non-existing list
        with pytest.raises(PlaylistDoesNotExistException):
            db.tag_playlist("non-existing", ["tag1", "tag4"])


def test_list_tags(filled_database):
    with filled_database() as db:
        assert set(db.list_tags()) == {"tag1", "tag2"}

        db.tag_playlist("pl3", ["tag3"])
        assert set(db.list_tags()) == {"tag1", "tag2", "tag3"}

        db.tag_playlist("pl1", [])
        assert set(db.list_tags()) == {"tag1", "tag3"}


def test_add_videos(filled_database):
    with filled_database() as db:
        pl = Playlist("pl1", "a", False)
        videos = [
            Video(
                title="title5",
                url="url5",
                description="",
                publish_date=4.5,
                watch_date=None,
                duration=5.0,
                thumbnail_url=None,
                extractor_hash="e_hash 5"
            ),
            Video(
                title="title",
                url="url6",
                description="",
                publish_date=4.5,
                watch_date=None,
                duration=5.0,
                thumbnail_url=None,
                extractor_hash="e_hash 6"
            )
        ]
        db.add_videos(videos, pl)
        pl1_videos = list(db.list_videos(playlists=["pl1"]))
        assert len(pl1_videos) == 4

        with pytest.raises(PlaylistDoesNotExistException):
            db.add_videos(videos, Playlist("non-existent", "", False))

        # Call without videos is silently ignored
        db.add_videos([], pl)


def test_marked_watched(filled_database):
    with filled_database() as db:
        id1_video = next(db.list_videos(ids=[1]).__iter__())
        assert not id1_video.watched
        db.mark_watched(1)

        id1_video = next(db.list_videos(ids=[1]).__iter__())
        assert id1_video.watched

        id2_video = next(db.list_videos(ids=[2]).__iter__())
        db.mark_watched(id2_video)
        id2_video = next(db.list_videos(ids=[2]).__iter__())
        assert id2_video.watched

        # Non-existent videos are silently ignored
        db.mark_watched(100)

        with pytest.raises(TypeError):
            db.mark_watched(1.0)


def test_marked_unwatched(filled_database):
    with filled_database() as db:
        id3_video = next(db.list_videos(ids=[3]).__iter__())
        assert id3_video.watched
        db.mark_unwatched(3)

        id3_video = next(db.list_videos(ids=[3]).__iter__())
        assert not id3_video.watched


def test_list_videos(filled_database):
    def check_result(result: Iterable[MappedVideo], expected_ids: List[int]):
        assert len(list(result)) == len(expected_ids)
        for video in result:
            assert video.id in expected_ids
            assert VIDEOS[video.id] == video

    with filled_database() as db:
        check_result(db.list_videos(ids=[1, 2, 3]), [1, 2, 3])
        check_result(db.list_videos(ids=[1, 2, 3], watched=False), [1, 2])
        check_result(db.list_videos(ids=[1, 2, 3], watched=True), [3])
        check_result(db.list_videos(tags=["tag1", "tag2"]), [1, 2])
        check_result(db.list_videos(playlists=["pl1", "pl2"]), [1, 2, 3])
        check_result(db.list_videos(playlists=["pl4"]), [])


def test_cleanup(filled_database):
    with filled_database() as db:
        db.cleanup(keep=0)
        assert len(list(db.list_videos())) == 2
