# Copyright (C) 2018  Wolfgang Popp
# ytcc - The YouTube channel checker
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

import itertools
import shutil
import signal
import textwrap as wrap
import readline
from collections import namedtuple
from datetime import datetime
from ytcc import core
from ytcc import arguments

Command = namedtuple("Command", ["name", "shortcuts", "help", "action"])
ytcc_core = core.Ytcc()
interactive_enabled = True
description_enabled = True
no_video = False
download_path = None

header_enabled = True
table_header = [_("ID"), _("Date"), _("Channel"), _("Title"), _("URL"), _("Watched")]
column_filter = [ytcc_core.config.table_format.getboolean("ID"),
                 ytcc_core.config.table_format.getboolean("Date"),
                 ytcc_core.config.table_format.getboolean("Channel"),
                 ytcc_core.config.table_format.getboolean("Title"),
                 ytcc_core.config.table_format.getboolean("URL"),
                 ytcc_core.config.table_format.getboolean("Watched")]


def update_all():
    print(_("Updating channels..."))
    ytcc_core.update_all()


def maybe_print_description(description):
    global description_enabled
    if description_enabled:
        columns = shutil.get_terminal_size().columns
        delimiter = "=" * columns
        lines = description.splitlines()

        print()
        print(_("Video description:"))
        print(delimiter)

        for line in lines:
            print(wrap.fill(line, width=columns))

        print(delimiter, end="\n\n")


def interactive_prompt(video):
    executed_cmd = False
    RETURN_VAL_HELP = 0
    RETURN_VAL_QUIT = 1

    def print_help():
        print()
        print(_("Available commands:"))
        for command in commands:
            print("{:>20}  {:<2}  {}".format(command.name, command.shortcuts[0], command.help))
        print()
        return RETURN_VAL_HELP

    commands = [
        Command("help", ["h"], _("print this help"), print_help),
        Command("yes", ["y", ""], _("play the video"), lambda: play(video, no_video)),
        Command("no", ["n"], _("do not play the video"), lambda: None),
        Command("mark", ["m"], _("mark the video watched without playing it"),
                lambda: ytcc_core.mark_watched([video.id])),
        Command("audio", ["a"], _("play only the audio track of the video"),
                lambda: play(video, True)),
        Command("download-video", ["dv"], _("download the video"),
                lambda: download([video.id], False)),
        Command("download-audio", ["da"], _("download the audio track of the video"),
                lambda: download([video.id], True)),
        Command("quit", ["q", "exit"], _("exit ytcc"), lambda: RETURN_VAL_QUIT),
    ]

    def completer(text, state):
        options = [cmd[0] for cmd in commands if cmd[0].startswith(text)]
        if state < len(options):
            return options[state]
        return None

    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" ")
    readline.set_completer(completer)

    while not executed_cmd:
        try:
            question = _('Play video "%(title)s" by "%(channel)s"?') % {
                "title": video.title,
                "channel": video.channelname
            }
            choice = input(question + '\n[y(es)/n(o)/a(udio)/m(ark)/q(uit)/h(elp)] (Default: y): ')
        except EOFError:
            print()
            return False

        executed_cmd = True
        invalid_cmd = True
        choice = choice.lower()

        for cmd in commands:
            if choice in (cmd.name, *cmd.shortcuts):
                result = cmd.action()
                if result == RETURN_VAL_QUIT:
                    return False
                if result == RETURN_VAL_HELP:
                    executed_cmd = False
                invalid_cmd = False
                break

        if invalid_cmd:
            print()
            print(_("'%(cmd)s' is an invalid command. Type 'help' for more info.\n") % {
                "cmd": choice
            })
            executed_cmd = False

    return True


def play(video, audio_only):
    maybe_print_description(video.description)
    if not ytcc_core.play_video(video.id, audio_only):
        print()
        print(_("WARNING: The video player terminated with an error.\n"
                "         The last video is not marked as watched!"))
        print()


def watch(video_ids=None):
    if not video_ids:
        videos = ytcc_core.list_videos()
    else:
        videos = ytcc_core.get_videos(video_ids)

    if not videos:
        print(_("No videos to watch. No videos match the given criteria."))
    else:
        for video in videos:
            if interactive_enabled:
                if not interactive_prompt(video):
                    break
            else:
                print(_('Playing "%(video)s" by "%(channel)s"...') % {
                    "video": video.title,
                    "channel": video.channelname
                })
                play(video, no_video)


def table_print(header, table):
    col_widths = []
    header_line = ""

    for h in header:
        col_widths.append(len(h))

    for i in range(0, len(header)):
        col_widths[i] = max(col_widths[i], max(map(lambda h: len(str(h[i])), table)))

    for width in col_widths:
        header_line += "─" * (width + 2)
        header_line += "┼"

    header_line = header_line[:-1]
    table_format = (" {{:<{}}} │" * len(header))[:-2].format(*col_widths)

    if header_enabled:
        print(table_format.format(*header))
        print(header_line)

    for row in table:
        print(table_format.format(*row))


def print_videos(videos):

    def row_filter(row):
        return list(itertools.compress(row, column_filter))

    def video_to_list(video):
        return [video.id, datetime.fromtimestamp(video.publish_date).strftime("%Y-%m-%d %H:%M"),
                video.channelname, video.title, ytcc_core.get_youtube_video_url(video.yt_videoid),
                _("Yes") if video.watched else _("No")]

    table = [row_filter(video_to_list(v)) for v in videos]
    table_print(row_filter(table_header), table)


def mark_watched(video_ids):
    marked_videos = ytcc_core.mark_watched(video_ids)
    if not marked_videos:
        print(_("No videos were marked as watched"))
    else:
        print(_("Following videos were marked as watched:"))
        print()
        print_videos(marked_videos)


def list_videos():
    videos = ytcc_core.list_videos()
    if not videos:
        print(_("No videos to list. No videos match the given criteria."))
    else:
        print_videos(videos)


def print_channels():
    channels = ytcc_core.get_channels()
    if not channels:
        print(_("No channels added, yet."))
    else:
        for channel in channels:
            print(channel.displayname)


def add_channel(name, channel_url):
    try:
        ytcc_core.add_channel(name, channel_url)
    except core.BadURLException:
        print(_("'%r' is not a valid YouTube URL") % channel_url)
    except core.DuplicateChannelException:
        print(_("You are already subscribed to '%r'") % name)
    except core.ChannelDoesNotExistException:
        print(_("The channel '%r' does not exist") % channel_url)


def cleanup():
    print(_("Cleaning up database..."))
    ytcc_core.cleanup()


def import_channels(file):
    print(_("Importing..."))
    try:
        ytcc_core.import_channels(file)
        subscriptions = _("Subscriptions")
        print()
        print(subscriptions)
        print("=" * len(subscriptions))
        print_channels()
    except core.InvalidSubscriptionFileError:
        print(_("The given file is not valid YouTube export file"))


def download(video_ids, no_video):
    try:
        ytcc_core.download_videos(video_ids=video_ids, path=download_path, no_video=no_video)
    except core.DownloadError:
        print(_("An Error occured while downloading the video"))


def run():

    args = arguments.get_args()

    option_executed = False

    if args.version:
        import ytcc
        print("ytcc version " + ytcc.__version__)
        print()
        print("Copyright (C) 2015-2018  " + ytcc.__author__)
        print("This program comes with ABSOLUTELY NO WARRANTY; This is free software, and you")
        print("are welcome to redistribute it under certain conditions.  See the GNU General ")
        print("Public Licence for details.")
        return

    if args.bug_report_info:
        import ytcc
        import youtube_dl
        import subprocess
        print("---ytcc version---")
        print(ytcc.__version__)
        print()
        print("---youtube-dl version---")
        print(youtube_dl.version.__version__)
        print()
        print("---mpv version---")
        subprocess.run(["mpv", "--version"])
        print()
        print("---config dump---")
        print(ytcc_core.config)
        return

    if args.yes:
        global interactive_enabled
        interactive_enabled = False

    if args.no_description:
        global description_enabled
        description_enabled = False

    if args.no_header:
        global header_enabled
        header_enabled = False

    if args.no_video:
        global no_video
        no_video = True

    if args.path:
        global download_path
        download_path = args.path

    if args.include_watched:
        ytcc_core.set_include_watched_filter()
        global column_filter
        column_filter[5] = True

    if args.columns:
        column_filter = [True if f in args.columns else False for f in table_header]

    if args.channel_filter:
        ytcc_core.set_channel_filter(args.channel_filter)

    if args.since:
        ytcc_core.set_date_begin_filter(args.since)

    if args.to:
        ytcc_core.set_date_end_filter(args.to)

    if args.search:
        ytcc_core.set_search_filter(args.search)

    if args.import_from:
        import_channels(args.import_from)
        option_executed = True

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
        ytcc_core.delete_channels(args.delete_channel)
        option_executed = True

    if args.update:
        if option_executed:
            print()
        update_all()
        option_executed = True

    if args.list:
        if option_executed:
            print()
        list_videos()
        option_executed = True

    if args.download is not None:
        if option_executed:
            print()
        download(args.download, no_video)
        option_executed = True

    if args.watch is not None:
        if option_executed:
            print()
        watch(args.watch)
        option_executed = True

    if args.mark_watched is not None:
        if option_executed:
            print()
        mark_watched(args.mark_watched)
        option_executed = True

    if not option_executed:
        update_all()
        print()
        list_videos()
        print()
        watch()


def register_signal_handlers():
    def handler(signum, frame):
        print()
        print(_("Bye..."))
        exit(1)

    signal.signal(signal.SIGINT, handler)


def main():
    register_signal_handlers()
    run()
