# ytcc - The YouTube channel checker
# Copyright (C) 2015  Wolfgang Popp
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

from ytcc import core
import shutil
import argparse
import os
import textwrap as wrap

ytcc_core = core.Ytcc()
interactive_enabled = True
description_enabled = True
channel_filter = None


def update_all():
    print("Updating channels...")
    ytcc_core.update_all()


def print_description(description):
    global description_enabled
    if description_enabled:
        columns = shutil.get_terminal_size().columns
        delimiter = "=" * columns
        lines = description.splitlines()

        print("\nVideo description:")
        print(delimiter)

        for line in lines:
            print(wrap.fill(line, width=columns))

        print(delimiter, end="\n\n")


def play_videos(videos, interactive):
    for video in videos:
        if interactive:
            choice = input('Play video "' + video.title + '" by "' + video.channelname +
                           '"?\n[y(es)/n(o)/m(ark)/q(uit)] (Default: y): ')
        else:
            print('Playing "' + video.title + '" by "' + video.channelname + '"...')
            choice = "y"

        if choice in ("y", "Y", "", "yes"):
            print_description(video.description)
            ytcc_core.play_video(video.id)
        elif choice in ("m", "M", "mark"):
            ytcc_core.mark_some_watched([video.id])
        elif choice in ("q", "Q", "quit"):
            break


def watch(video_ids=None):
    if not video_ids:
        unwatched_videos = ytcc_core.list_unwatched_videos(channel_filter)
        if not unwatched_videos:
            print("No unwatched videos to play.")
        else:
            play_videos(unwatched_videos, interactive_enabled)
    else:
        play_videos(ytcc_core.get_videos(video_ids), False)


def print_unwatched_videos():
    unwatched_videos = ytcc_core.list_unwatched_videos(channel_filter)
    if not unwatched_videos:
        print("No unwatched videos.")
    else:
        for video in unwatched_videos:
            print(video.id, " " + video.channelname + ": " + video.title)


def print_recent_videos():
    recent_videos = ytcc_core.list_recent_videos(channel_filter)
    if not recent_videos:
        print("No videos were added recently.")
    else:
        for video in recent_videos:
            print(video.id, " " + video.channelname + ": " + video.title)


def print_channels():
    channels = ytcc_core.list_channels()
    if not channels:
        print("No channels added, yet.")
    else:
        for channel in channels:
            print(channel.displayname)


def download(video_ids, path):
    ids = video_ids if video_ids else map(lambda video: video.id, ytcc_core.list_unwatched_videos(channel_filter))
    ytcc_core.download_videos(ids, path)


def add_channel(name, channel_url):
    try:
        ytcc_core.add_channel(name, channel_url)
    except core.BadURLException as e:
        print(e.message)
    except core.DuplicateChannelException as e:
        print(e.message)
    except core.ChannelDoesNotExistException as e:
        print(e.message)


def mark_watched(video_ids):
    if not video_ids or video_ids[0] == "all":
        ytcc_core.mark_watched(channel_filter)
    else:
        ytcc_core.mark_some_watched(video_ids)

def cleanup():
    print("Cleaning up database...")
    ytcc_core.cleanup()

def is_directory(string):
    if not os.path.isdir(string):
        msg = "%r is not a directory" % string
        raise argparse.ArgumentTypeError(msg)

    return string


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("-a", "--add-channel",
                        help="add a new channel. NAME is the name displayed by ytcc. URL is"
                        " the url of the channel's front page",
                        nargs=2,
                        metavar=("NAME", "URL"))

    parser.add_argument("-c", "--list-channels",
                        help="print a list of all subscribed channels",
                        action="store_true")

    parser.add_argument("-r", "--delete-channel",
                        help="unsubscribe from the channel identified by 'ID'",
                        metavar="ID",
                        type=str)

    parser.add_argument("-u", "--update",
                        help="update the video list",
                        action="store_true")

    parser.add_argument("-w", "--watch",
                        help="play the videos identified by 'ID'. Omitting the ID will "
                        "play all unwatched videos",
                        nargs='*',
                        type=int,
                        metavar="ID")

    parser.add_argument("-f", "--channel-filter",
                        help="plays, marks, downloads only videos from channels defined in "
                        "the filter",
                        nargs='+',
                        type=str,
                        metavar="NAME")

    parser.add_argument("-d", "--download",
                        help="download the videos identified by 'ID'. The videos are saved "
                        "in $HOME/Downloads by default. Omitting the ID will download "
                        "all unwatched videos",
                        nargs="*",
                        type=int,
                        metavar="ID")

    parser.add_argument("-p", "--path",
                        help="set the download path to PATH",
                        metavar="PATH",
                        type=is_directory)

    parser.add_argument("-g", "--no-description",
                        help="do not print the video description before playing the video",
                        action="store_true")

    parser.add_argument("-m", "--mark-watched",
                        help="mark videos identified by ID as watched. Omitting the ID "
                        "will mark all videos as watched",
                        nargs='*',
                        type=int,
                        metavar="ID")

    parser.add_argument("-l", "--list-unwatched",
                        help="print a list of unwatched videos",
                        action="store_true")

    parser.add_argument("-n", "--list-recent",
                        help="print a list of videos that were recently added",
                        action="store_true")

    parser.add_argument("-y", "--yes",
                        help="automatically answer all questions with yes",
                        action="store_true")

    parser.add_argument("--cleanup",
                        help="removes old videos from the database and shrinks the size of the database file",
                        action="store_true")

    parser.add_argument("-v", "--version",
                        help="output version information and exit",
                        action="store_true")

    args = parser.parse_args()

    option_executed = False

    if args.version:
        import ytcc
        print("ytcc version " + ytcc.__version__)
        print()
        print("Copyright (C) 2015  " + ytcc.__author__)
        print("This program comes with ABSOLUTELY NO WARRANTY; This is free software, and you")
        print("are welcome to redistribute it under certain conditions.  See the GNU General ")
        print("Public Licence for details.")
        return

    if args.yes:
        global interactive_enabled
        interactive_enabled = False

    if args.no_description:
        global description_enabled
        description_enabled = False

    if args.channel_filter:
        global channel_filter
        channel_filter = args.channel_filter

    if args.cleanup:
        cleanup()
        option_executed = True

    if args.add_channel:
        add_channel(*args.add_channel)
        option_executed = True

    if args.list_channels:
        print_channels()
        option_executed = True

    if args.delete_channel:
        ytcc_core.delete_channel(args.delete_channel)
        option_executed = True

    if args.download is not None:
        download(args.download, args.path)
        option_executed = True

    if args.update:
        if option_executed:
            print()
        update_all()
        option_executed = True

    if args.list_unwatched:
        if option_executed:
            print()
        print_unwatched_videos()
        option_executed = True

    if args.watch is not None:
        if option_executed:
            print()
        watch(args.watch)
        option_executed = True

    if args.mark_watched is not None:
        mark_watched(args.mark_watched)
        option_executed = True

    if args.list_recent:
        if option_executed:
            print()
        print_recent_videos()
        option_executed = True

    if not option_executed:
        update_all()
        print()
        watch()
