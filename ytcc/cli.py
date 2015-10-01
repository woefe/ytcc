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

ytcc = core.Ytcc()
interactive = True
descriptionEnabled = True
channelFilter = None

def update_all():
    print("Updating channels...")
    ytcc.update_all()

def watch_all():
    global interactive
    unwatchedVideos = ytcc.list_unwatched_videos()
    if not unwatchedVideos:
        print("You have already watched all videos.")
    else:
        for vID, title, description, publish_date, channel in unwatchedVideos:
            choice = input("Play video \"" + title + "\" by \"" + channel + "\"? [Y/n/m/a]: ") if interactive else "y"
            if choice in ( "y", "Y", ""):
                print_description(description)
                ytcc.play_video(vID)
            if choice in ( "m", "M"):
                ytcc.mark_watched(vID)
            elif choice in ("a", "A"):
                break

def print_description(description):
    global descriptionEnabled
    if descriptionEnabled:
        columns = shutil.get_terminal_size().columns
        delimiter = "=" * columns
        print("\nVideo description:")
        print(delimiter)
        print(description)
        print(delimiter, end="\n\n")

def watch_some(vIDs):
    for vID in vIDs:
        info = ytcc.get_video_info(vID)
        if info:
            vID, title, description, publish_date, channel = info
            print('Playing "' + title + '" by "' + channel + '"...')
            print_description(description)
            ytcc.play_video(vID)

def watch(vIDs):
    if not vIDs or vIDs[0] == "all":
        watch_all()
    else:
        watch_some(vIDs)

def print_unwatched_videos():
    unwatchedVideos = ytcc.list_unwatched_videos()
    if not unwatchedVideos:
        print("You have already watched all videos.")
    else:
        for vID, title, description, publish_date, channel in unwatchedVideos:
            print(vID, " " + channel + ": " + title)

def print_recent_videos():
    recentVideos = ytcc.list_recent_videos(channelFilter)
    if not recentVideos:
        print("No videos were added recently.")
    else:
        for vID, title, description, publish_date, channel in recentVideos:
            print(vID, " " + channel + ": " + title)

def print_channels():
    channels = ytcc.list_channels()
    if not channels:
        print("No channels added, yet.")
    else:
        for cID, name in channels:
            print(cID, " " + name)

def download(vIDs, path):
    download_dir = path[0] if path else os.path.expanduser("~") + "/Downloads"
    for vID in vIDs:
        ytcc.download_video(vID, download_dir)

def add_channel(name, channelURL):
    try:
        ytcc.add_channel(name, channelURL)
    except core.BadURLException as e:
        print(e.message)
    except core.DuplicateChannelException as e:
        print(e.message)
    except core.ChannelDoesNotExistException as e:
        print(e.message)

def mark_watched(vIDs):
    if not vIDs or vIDs[0] == "all":
        ytcc.mark_all_watched()
    else:
        ytcc.mark_some_watched(vIDs)

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
            type=int)

    parser.add_argument("-u", "--update",
            help="update the videolist",
            action="store_true")

    parser.add_argument("-w", "--watch",
            help="play the videos identified by 'ID'. Leaving out the ID will "
                 "play all unwatched videos",
            nargs='*',
            metavar="ID")

    parser.add_argument("-f", "--channel_filter",
            help="defines a filter on which channels to watch",
            nargs='+',
            metavar="ID")

    parser.add_argument("-d", "--download",
            help="download the videos identified by 'ID'. The videos are saved "
                 "in $HOME/Downloads by default",
            nargs="+",
            metavar="ID")

    parser.add_argument("-p", "--path",
            help="set the download path to PATH.",
            nargs=1,
            metavar="PATH")

    parser.add_argument("-g", "--no-description",
            help="do not print the video description before playing the video",
            action="store_true")

    parser.add_argument("-m", "--mark-watched",
            help="mark videos identified by ID as watched. Leaving out the ID "
                 "will mark all videos as watched",
            nargs='*',
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

    parser.add_argument("-v", "--version",
            help="output version information and exit",
            action="store_true")

    args = parser.parse_args()

    print(args)

    optionExecuted = False

    if args.version:
        import ytcc
        print("ytcc version " + ytcc.__version__)
        print()
        print("Copyright (C) 2015  "  + ytcc.__author__)
        print("This program comes with ABSOLUTELY NO WARRANTY; This is free software, and you")
        print("are welcome to redistribute it under certain conditions.  See the GNU General ")
        print("Public Licence for details.")
        return

    if args.yes:
        global interactive
        interactive = False

    if args.no_description:
        global descriptionEnabled
        descriptionEnabled = False

    if args.channel_filter:
        global channelFilter
        channelFilter = args.channel_filter

    if args.add_channel:
        add_channel(*args.add_channel)
        optionExecuted = True

    if args.list_channels:
        print_channels()
        optionExecuted = True

    if args.delete_channel:
        ytcc.delete_channel(args.delete_channel)
        optionExecuted = True

    if args.download:
        download(args.download, args.path)
        optionExecuted = True

    if args.update:
        if optionExecuted:
            print()
        update_all()
        optionExecuted = True

    if args.list_unwatched:
        if optionExecuted:
            print()
        print_unwatched_videos()
        optionExecuted = True

    if args.watch is not None:
        if optionExecuted:
            print()
        watch(args.watch)
        optionExecuted = True

    if args.mark_watched is not None:
        mark_watched(args.mark_watched)
        optionExecuted = True

    if args.list_recent:
        if optionExecuted:
            print()
        print_recent_videos()
        optionExecuted = True

    if not optionExecuted:
        update_all()
        print()
        watch_all()

