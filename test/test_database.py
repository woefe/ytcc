import sqlite3
import unittest
from nose.tools import raises
from ytcc.database import Database
from ytcc.video import Video

insert_list = [("0", "title1", "description1", "id_publisher1", 1488286166, 0),
               ("0", "title1", "description1", "id_publisher1", 1488286167, 0),
               ("0", "title2", "description1", "id_publisher1", 1488286168, 0),
               ("1", "title2", "description2", "id_publisher2", 1488286170, 0),
               ("2", "title3", "description3", "id_publisher2", 1488286171, 0)]


def init_db():
    db = Database(":memory:")
    db.add_channel("publisher1", "id_publisher1")
    db.add_channel("publisher2", "id_publisher2")
    db.add_channel("publisher3", "id_publisher3")
    db.add_videos(insert_list)
    return db


class DatabaseTest(unittest.TestCase):

    @raises(sqlite3.IntegrityError)
    def test_add_channel_duplicate(self):
        db = Database(":memory:")
        db.add_channel("Webdriver Torso", "UCsLiV4WJfkTEHH0b9PmRklw")
        db.add_channel("Webdriver Torso2", "UCsLiV4WJfkTEHH0b9PmRklw")

    def test_add_and_get_channels(self):
        db = Database(":memory:")
        db.add_channel("Webdriver Torso", "UCsLiV4WJfkTEHH0b9PmRklw")
        db.add_channel("Webdriver YPP", "UCxexYYtOetqikZqriLuTS-g")
        channels = db.get_channels()
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels[0].displayname, "Webdriver Torso")
        self.assertEqual(channels[0].yt_channelid, "UCsLiV4WJfkTEHH0b9PmRklw")
        self.assertEqual(channels[1].displayname, "Webdriver YPP")
        self.assertEqual(channels[1].yt_channelid, "UCxexYYtOetqikZqriLuTS-g")

    def test_add_and_get_videos(self):
        db = init_db()
        db.add_videos(insert_list)
        videos = db.get_videos(end_timestamp=1488286171, include_watched=True)
        self.assertEqual(len(videos), 2)
        self.assertEqual(videos[0].yt_videoid, "0")
        self.assertEqual(videos[1].yt_videoid, "1")

    def test_search(self):
        db = init_db()
        result = db.search("title2")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].yt_videoid, "1")

    def test_delete_channels(self):
        db = init_db()
        db.delete_channels(["publisher1", "publisher2"])
        channels = db.get_channels()
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0].displayname, "publisher3")

    def test_resolve_video_id(self):
        db = init_db()
        video = db.resolve_video_id(1)
        expected = Video(1, "0", "title1", "description1", 1488286166, "publisher1", False)
        self.assertEqual(video, expected)

    def test_mark_watched(self):
        db = init_db()
        db.mark_watched([2, 3])
        videos = db.get_videos(end_timestamp=1488286172, include_watched=False)
        expected = Video(1, "0", "title1", "description1", 1488286166, "publisher1", False)
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0], expected)
