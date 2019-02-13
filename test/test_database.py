from unittest import TestCase

import sqlalchemy
from nose.tools import raises
from ytcc.database import Database, Video, Channel

insert_list = [
    dict(yt_videoid="0", title="title1", description="description1", publisher="id_publisher1", publish_date=1488286166,
         watched=False),
    dict(yt_videoid="0", title="title1", description="description1", publisher="id_publisher1", publish_date=1488286167,
         watched=False),
    dict(yt_videoid="0", title="title2", description="description1", publisher="id_publisher1", publish_date=1488286168,
         watched=False),
    dict(yt_videoid="1", title="title2", description="description2", publisher="id_publisher2", publish_date=1488286170,
         watched=False),
    dict(yt_videoid="2", title="title3", description="description3", publisher="id_publisher2", publish_date=1488286171,
         watched=False)
]


def init_db():
    db = Database(":memory:")
    db.add_channel(Channel(displayname="publisher1", yt_channelid="id_publisher1"))
    db.add_channel(Channel(displayname="publisher2", yt_channelid="id_publisher2"))
    db.add_channel(Channel(displayname="publisher3", yt_channelid="id_publisher3"))
    db.add_videos(insert_list)
    return db


class DatabaseTest(TestCase):

    @raises(sqlalchemy.exc.IntegrityError)
    def test_add_channel_duplicate(self):
        db = Database(":memory:")
        db.add_channel(Channel(displayname="Webdriver Torso", yt_channelid="UCsLiV4WJfkTEHH0b9PmRklw"))
        db.add_channel(Channel(displayname="Webdriver Torso2", yt_channelid="UCsLiV4WJfkTEHH0b9PmRklw"))

    def test_add_and_get_channels(self):
        db = Database(":memory:")
        db.add_channel(Channel(displayname="Webdriver Torso", yt_channelid="UCsLiV4WJfkTEHH0b9PmRklw"))
        db.add_channel(Channel(displayname="Webdriver YPP", yt_channelid="UCxexYYtOetqikZqriLuTS-g"))
        channels = db.get_channels()
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels[0].displayname, "Webdriver Torso")
        self.assertEqual(channels[0].yt_channelid, "UCsLiV4WJfkTEHH0b9PmRklw")
        self.assertEqual(channels[1].displayname, "Webdriver YPP")
        self.assertEqual(channels[1].yt_channelid, "UCxexYYtOetqikZqriLuTS-g")

    def test_add_and_get_videos(self):
        db = init_db()
        db.add_videos(insert_list)
        videos = db.session.query(Video).all()
        self.assertEqual(len(videos), 3)
        self.assertEqual(videos[0].yt_videoid, "0")
        self.assertEqual(videos[1].yt_videoid, "1")
        self.assertEqual(videos[2].yt_videoid, "2")

    def test_delete_channels(self):
        db = init_db()
        db.delete_channels(["publisher1", "publisher2"])
        channels = db.get_channels()
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0].displayname, "publisher3")

    def test_resolve_video_id(self):
        db = init_db()
        video = db.resolve_video_id(1)
        expected = Video(id=1, yt_videoid="0", title="title1", description="description1", publisher="id_publisher1",
                         publish_date=1488286166.0, watched=False)

        self.eq_video(video, expected)

    def test_mark_watched(self):
        db = init_db()
        for video in db.resolve_video_ids([2, 3]):
            video.watched = True
        videos = db.session.query(Video).filter(Video.watched == False).all()
        expected = Video(id=1, yt_videoid="0", title="title1", description="description1", publisher="id_publisher1",
                         publish_date=1488286166.0, watched=False)
        self.assertEqual(len(videos), 1)
        self.eq_video(videos[0], expected)

    def eq_video(self, video: Video, expected: Video) -> None:
        self.assertEqual(video.id, expected.id)
        self.assertEqual(video.yt_videoid, expected.yt_videoid)
        self.assertEqual(video.title, expected.title)
        self.assertEqual(video.description, expected.description)
        self.assertEqual(video.publish_date, expected.publish_date)
        self.assertEqual(video.publisher, expected.publisher)
        self.assertEqual(video.watched, expected.watched)
