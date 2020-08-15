#  ytcc - The YouTube channel checker
#  Copyright (C) 2020  Wolfgang Popp
#
#  This file is part of ytcc.
#
#  ytcc is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  ytcc is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with ytcc.  If not, see <http://www.gnu.org/licenses/>.
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Callable, TypeVar, Generic, Optional

import click

from ytcc import core
from ytcc import __version__, __author__
from ytcc.printer import JSONPrinter, XSVPrinter, VideoPrintable, TablePrinter, PlaylistPrintable
from ytcc.tui import print_meta

T = TypeVar("T")

ytcc = core.Ytcc()
printer = JSONPrinter()


class CommaList(click.ParamType, Generic[T]):

    def __init__(self, validator: Callable[[str], T]):
        self.validator = validator

    def convert(self, value, param, ctx) -> List[T]:
        try:
            return [self.validator(elem.strip()) for elem in value.split(",")]
        except:
            self.fail(f"Unexpected value {value}")


version_text = f"""%(prog)s, version %(version)s

Copyright (C) 2015-2020  {__author__}
This program comes with ABSOLUTELY NO WARRANTY; This is free software, and you
are welcome to redistribute it under certain conditions.  See the GNU General
Public Licence for details."""


@click.group()
@click.option("--config", type=click.Path())
@click.option("--verbose", is_flag=True)
@click.option("--output", type=click.Choice(["json", "table", "xsv"]), default="table")
@click.option("--separator", default=",", show_default=True)
@click.version_option(version=__version__, prog_name="ytcc", message=version_text)
def cli(config, verbose, output, separator):
    global ytcc, printer

    ytcc = core.Ytcc(config)

    if output == "table":
        printer = TablePrinter()
    elif output == "json":
        printer = JSONPrinter()
    elif output == "xsv":
        printer = XSVPrinter(separator)


@cli.command()
@click.argument("name")
@click.argument("url")
def subscribe(name: str, url: str):
    ytcc.add_playlist(name, url)


@cli.command()
@click.argument("name")
def unsubscribe(name: str):
    ytcc.delete_playlist(name)


@cli.command()
@click.argument("old")
@click.argument("new")
def rename(old: str, new: str):
    ytcc.rename_playlist(old, new)


@cli.command()
@click.option("--attributes", type=CommaList(str))
def subscriptions(attributes: List[str]):
    printer.filter = attributes
    printer.print(PlaylistPrintable(ytcc.list_playlists()))


@cli.command()
@click.argument("name")
@click.argument("tags", nargs=-1)
def tag(name: str, tags: List[str]):
    ytcc.tag_playlist(name, tags)


@cli.command()
def update():
    ytcc.update()


@cli.command("list")
@click.option("--tags", type=CommaList(str))
@click.option("--since", type=click.DateTime(), default="1970-01-01")
@click.option("--till", type=click.DateTime(), default="9999-12-31")
@click.option("--playlists", type=CommaList(str))
@click.option("--ids", "-i", type=CommaList(int))
@click.option("--attributes", type=CommaList(str))
@click.option("--watched", is_flag=True, default=False)
def list_videos(tags: List[str], since: datetime, till: datetime, playlists: List[str],
                ids: List[int], attributes: List[str], watched: bool):
    ytcc.set_tags_filter(tags)
    ytcc.set_date_begin_filter(since)
    ytcc.set_date_end_filter(till)
    ytcc.set_playlist_filter(playlists)
    ytcc.set_video_id_filter(ids)
    ytcc.set_include_watched_filter(watched)
    printer.filter = attributes
    printer.print(VideoPrintable(ytcc.list_videos()))


@cli.command("ls")
def ls():
    ytcc.set_include_watched_filter(False)
    p = XSVPrinter()
    p.filter = ["id"]
    p.print(VideoPrintable(ytcc.list_videos()))


def _get_ids(ids) -> Optional[List[int]]:
    if not ids and not sys.stdin.isatty():
        ids = [int(line) for line in sys.stdin.readlines()]
    return list(ids) if ids else None


@cli.command()
@click.option("--audio-only", is_flag=True, default=False)
@click.option("--meta/--no-meta", is_flag=True, default=True)
@click.option("--mark/--no-mark", is_flag=True, default=True)
@click.argument("ids", nargs=-1)
@click.pass_context
def play(ctx: click.Context, ids: Optional[List[int]], audio_only: bool, meta: bool, mark: bool):
    ytcc.set_video_id_filter(_get_ids(ids))
    videos = ytcc.list_videos()

    if not videos:
        # TODO
        print("No videos to watch. No videos match the given criteria.")
        ctx.exit(0)

    for video in videos:
        if meta:
            print_meta(video)
        if ytcc.play_video(video, audio_only) and mark:
            ytcc.mark_watched(video)
        elif mark:
            print()
            print(("WARNING: The video player terminated with an error.\n"
                   "         The last video is not marked as watched!"))
            print()


@cli.command()
@click.argument("ids", nargs=-1)
def mark(ids: Optional[List[int]]):
    ytcc.mark_watched(_get_ids(ids))


@cli.command()
@click.option("--path", type=click.Path(file_okay=False, dir_okay=True))
@click.argument("ids", nargs=-1)
def download():
    pass


@cli.command()
def tui():
    pass


@cli.command()
def cleanup():
    ytcc.cleanup()


@cli.command()
def bug_report():
    # pylint: disable=import-outside-toplevel
    import youtube_dl.version
    import subprocess
    import sys
    from ytcc import __version__
    print("---ytcc version---")
    print(__version__)
    print()
    print("---youtube-dl version---")
    print(youtube_dl.version.__version__)
    print()
    print("---python version---")
    print(sys.version)
    print()
    print("---mpv version---")
    subprocess.run(["mpv", "--version"], check=False)
    print()
    print("---config dump---")
    print(ytcc.config)
