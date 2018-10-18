import os
from datetime import datetime
from unittest import TestCase
from nose.tools import raises
from ytcc.core import Ytcc
from ytcc.core import DuplicateChannelException
from ytcc.core import BadURLException

class TestYtcc(TestCase):

    def setUp(self):
        self.current_dir = os.path.dirname(__file__)
        self.ytcc = Ytcc(os.path.join(self.current_dir, "data/ytcc_test.conf"))
        self.db_conn = self.ytcc.db

    def tearDown(self):
        self.db_conn._execute_query("delete from video")
        self.db_conn._execute_query("delete from channel")

    def test_add_channel_duplicate(self):
        ytcc = self.ytcc
        ytcc.add_channel("Webdriver Torso",
                         "https://www.youtube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw")
        self.assertRaises(DuplicateChannelException, ytcc.add_channel,
                "Fail", "https://www.youtube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw")

    def test_add_channel_bad_url(self):
        ytcc = self.ytcc
        self.assertRaises(BadURLException, ytcc.add_channel,
                "Fail", "yotube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw")

    def test_add_and_get_channels(self):
        ytcc = self.ytcc
        ytcc.add_channel("Webdriver Torso", "https://www.youtube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw")
        ytcc.add_channel("Webdriver YPP", "https://www.youtube.com/channel/UCxexYYtOetqikZqriLuTS-g")
        channels = ytcc.get_channels()
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels[0].displayname, "Webdriver Torso")
        self.assertEqual(channels[1].displayname, "Webdriver YPP")

    def test_import_channels(self):
        ytcc = self.ytcc
        ytcc.import_channels(open(os.path.join(self.current_dir, "data/subscriptions")))
        self.assertEqual(len(ytcc.get_channels()), 58)



class TestYtccPreparedChannels(TestCase):

    def setUp(self):
        self.current_dir = os.path.dirname(__file__)
        self.ytcc = Ytcc(os.path.join(self.current_dir, "data/ytcc_test.conf"))
        self.db_conn = self.ytcc.db
        self.db_conn.add_channel("Webdriver Torso", "UCsLiV4WJfkTEHH0b9PmRklw")
        self.db_conn.add_channel("Webdriver YPP", "UCxexYYtOetqikZqriLuTS-g")

    def tearDown(self):
        self.db_conn._execute_query("delete from video")
        self.db_conn._execute_query("delete from channel")

    def test_update_all(self):
        ytcc = self.ytcc
        ytcc.update_all()
        self.assertTrue(len(ytcc.list_videos()) > 10)

    def test_delete_channels(self):
        ytcc = self.ytcc
        ytcc.delete_channels(["Webdriver Torso"])
        channels = ytcc.get_channels()
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0].displayname, "Webdriver YPP")


class TestYtccPreparedVideos(TestCase):

    def setUp(self):
        self.current_dir = os.path.dirname(__file__)
        self.ytcc = Ytcc(os.path.join(self.current_dir, "data/ytcc_test.conf"))
        self.db_conn = self.ytcc.db

        insert_list = [
            ("V-ozGFl3Jks", "tmptYnCut", "", "UCsLiV4WJfkTEHH0b9PmRklw", 1488348731.0, 1),
            ("a1gOeiyIqPs", "tmp99Yc1l", "", "UCsLiV4WJfkTEHH0b9PmRklw", 1488348519.0, 1),
            ("0ounUgOrcqo", "tmppfXKp6", "", "UCsLiV4WJfkTEHH0b9PmRklw", 1488345630.0, 1),
            ("7mckB-NdKWY", "tmpiM62pN", "", "UCsLiV4WJfkTEHH0b9PmRklw", 1488345565.0, 0),
            ("RmRPt93uAsQ", "tmpIXBgjd", "", "UCsLiV4WJfkTEHH0b9PmRklw", 1488344217.0, 0),
            ("nDPy3RyKdrg", "tmpwA0TjG", "", "UCsLiV4WJfkTEHH0b9PmRklw", 1488343000.0, 0),
            ("L0_F805qUIM", "tmpKDOkro", "", "UCxexYYtOetqikZqriLuTS-g", 1488344253.0, 1),
            ("lXWrdlDEzQs", "tmpEvCR4s", "", "UCxexYYtOetqikZqriLuTS-g", 1488343152.0, 1),
            ("cCnXsCQNkr8", "tmp1rpsWK", "", "UCxexYYtOetqikZqriLuTS-g", 1488343046.0, 1),
            ("rSxVs0XeQa4", "tmpc5Y2pd", "", "UCxexYYtOetqikZqriLuTS-g", 1488342015.0, 0),
            ("gQAsWrGfsrw", "tmpn1M1Oa", "", "UCxexYYtOetqikZqriLuTS-g", 1488341324.0, 0),
        ]
        self.db_conn.add_channel("Webdriver Torso", "UCsLiV4WJfkTEHH0b9PmRklw")
        self.db_conn.add_channel("Webdriver YPP", "UCxexYYtOetqikZqriLuTS-g")
        self.db_conn.add_videos(insert_list)
        self.video_id = self.db_conn._execute_query_with_result(
            "select id from video where title = 'tmpIXBgjd';")[0][0]

    def tearDown(self):
        self.db_conn._execute_query("delete from video")
        self.db_conn._execute_query("delete from channel")

    def test_list_videos_no_filter(self):
        ytcc = self.ytcc
        videos = ytcc.list_videos()
        self.assertEqual(len(videos), 5)
        titles = set([v.title for v in videos])
        expected = {"tmpiM62pN", "tmpIXBgjd", "tmpwA0TjG", "tmpc5Y2pd", "tmpn1M1Oa"}
        self.assertSetEqual(set(titles), expected)

    def test_list_videos_search_filter(self):
        ytcc = self.ytcc
        ytcc.set_search_filter("title:tmpIXBgjd")
        videos = ytcc.list_videos()
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0].title, "tmpIXBgjd")

    def test_list_videos_channel_filter(self):
        ytcc = self.ytcc
        ytcc.set_channel_filter(["Webdriver Torso"])
        videos = ytcc.list_videos()
        self.assertEqual(len(videos), 3)
        self.assertEqual(videos[0].channelname, "Webdriver Torso")
        self.assertEqual(videos[1].channelname, "Webdriver Torso")
        self.assertEqual(videos[2].channelname, "Webdriver Torso")

    def test_list_videos_watched_filter(self):
        ytcc = self.ytcc
        ytcc.set_include_watched_filter()
        videos = ytcc.list_videos()
        self.assertEqual(len(videos), 11)

    def test_list_videos_date_filter(self):
        ytcc = self.ytcc
        ytcc.set_date_begin_filter(datetime.fromtimestamp(1488343000.0))
        ytcc.set_date_end_filter(datetime.fromtimestamp(1488345000.0))
        videos = ytcc.list_videos()
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0].title, "tmpIXBgjd")

    def test_list_videos_combined_filters(self):
        ytcc = self.ytcc
        ytcc.set_date_begin_filter(datetime.fromtimestamp(1488343000.0))
        ytcc.set_date_end_filter(datetime.fromtimestamp(1488346000.0))
        ytcc.set_include_watched_filter()
        ytcc.set_channel_filter(["Webdriver Torso"])
        videos = ytcc.list_videos()
        expected = {"tmppfXKp6", "tmpiM62pN", "tmpIXBgjd"}
        titles = set([v.title for v in videos])
        self.assertEqual(len(videos), 3)
        self.assertSetEqual(titles, expected)

    def test_resolve_video_ids(self):
        ytcc = self.ytcc
        videos = ytcc.get_videos([self.video_id])
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0].title, "tmpIXBgjd")

    def test_play_video(self):
        ytcc = self.ytcc
        ytcc.play_video(self.video_id)
        self.assertTrue(ytcc.get_videos([self.video_id])[0].watched)

    def test_download_videos(self):
        ytcc = self.ytcc
        success_ids = map(lambda a: a[0], filter(lambda a: a[1], ytcc.download_videos([self.video_id])))
        ytcc.mark_watched(list(success_ids))
        self.assertTrue(ytcc.get_videos([self.video_id])[0].watched)
        self.assertTrue(os.path.isfile(os.path.join(ytcc.config.download_dir, "tmpIXBgjd.webm")))

    def test_mark_all_watched(self):
        ytcc = self.ytcc
        ytcc.mark_watched()
        videos = ytcc.list_videos()
        self.assertEqual(len(videos), 0)

