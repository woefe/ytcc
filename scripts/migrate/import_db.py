import sys

from typing import List,Iterable
import pickle
import itertools

import ytcc
import ytcc.core
import ytcc.config

import youtube_dl

from common import ExportedVideo, ExportedChannel

if int(ytcc.__version__.split(".")[0]) != 2:
    print(f"ytcc v2 version should begin with 2, actually {ytcc.__version__}", file=sys.stderr)
    exit(1)

if __name__=="__main__":
    ytcc.config.load("./ytcc2.conf")
    ytcc2obj: ytcc.core.Ytcc = ytcc.core.Ytcc()

    print("Loading channels.pickle")
    with open("channels.pickle", "rb") as channelfile:
        channels: List[ExportedChannel] = pickle.load(channelfile)
    print("Adding channels")
    existing_channels=ytcc2obj.list_playlists()
    for channel in channels:
        print("Adding:", channel.name,
              f"https://www.youtube.com/channel/{channel.channelid}/videos")
        try:
            if len([i for i in existing_channels if i.name==channel.name])==1:
                print(f"A playlist with this name already exists. Skipping", file=sys.stderr)
            else:
                ytcc2obj.add_playlist(channel.name,
                                      f"https://www.youtube.com/channel/{channel.channelid}/videos")
        except ytcc.exceptions.BadURLException as ex:
            print("This channel doesn't exist any more, or has no content."
                + "Try checking it in the browser:"
                +f"https://www.youtube.com/channel/{channel.channelid}/videos", file=sys.stderr)
    print("Loading videos.pickle")
    with open("videos.pickle", "rb") as videofile:
        videos: List[ExportedVideo] = pickle.load(videofile)
    print("Adding videos")

    videos.sort(key=lambda v: v.pl_name)
    videos=iter(videos)
    while ((head:=next(videos, None))!=None):
        current_pl=head.pl_name
        print(f"Adding videos for {current_pl}")
        key=lambda v: (v.pl_name==current_pl)
        to_add=itertools.chain([head], itertools.takewhile(key, videos))
        videos=itertools.dropwhile(key, videos)
        try:
            ytcc2obj.database.add_videos([ytcc.core.Video(video.url, video.title,
                video.description, video.publish_date, video.watched, 0,
                video.extractor_hash) for video in to_add],
                ytcc.core.Playlist(current_pl, None))
        except ytcc.exceptions.PlaylistDoesNotExistException:
            print("This channel doesn't appear to have been added correctly. These videos will be skipped.", file=sys.stderr)
    print("Done")
