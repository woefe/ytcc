#!/usr/bin/env python

import sys

from typing import List

import pickle

import ytcc
import ytcc.core

from common import ExportedVideo, ExportedChannel

if int(ytcc.__version__.split(".")[0]) != 1:
	print(f"ytcc v1 version should begin with 1, actually {ytcc.__version__}", file=sys.stderr)
	exit(1)

def exportVideo(ytcc1obj: ytcc.core.Ytcc, video: ytcc.core.Video) -> ExportedVideo:
	return ExportedVideo(ytcc1obj.get_youtube_video_url(video.yt_videoid),
		video.title, video.description, video.publish_date, video.watched,
		video.channel.displayname, f"youtube {video.yt_videoid}")

if __name__=="__main__":
	ytcc1obj: ytcc.core.Ytcc = ytcc.core.Ytcc()

	ytcc1obj.set_include_watched_filter()
	videos: List[ytcc.core.Video] = ytcc1obj.list_videos()
	exportedvideos: List[ExportedVideo] = [exportVideo(ytcc1obj, vid) for vid in videos]

	channels: List[ytcc.core.Channel] = ytcc1obj.get_channels()
	exportedchannels: List[ExportedChannel] = [ExportedChannel(channel.yt_channelid, channel.displayname)
		for channel in channels]
	
	with open("videos.pickle", "xb") as videofile:
		pickle.dump(exportedvideos, videofile)
	with open("channels.pickle", "xb") as channelfile:
		pickle.dump(exportedchannels, channelfile)
