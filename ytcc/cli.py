# ytcc - The YouTube channel checker
# Copyright (C) 2020  Wolfgang Popp
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

import logging
import sys
from datetime import datetime
from pathlib import Path
from sqlite3 import DatabaseError
from typing import List, Callable, TypeVar, Generic, Optional, Iterable, Tuple

import click

from ytcc import __version__, __author__
from ytcc import core, config
from ytcc.config import PlaylistAttr, VideoAttr
from ytcc.database import MappedVideo
from ytcc.exceptions import BadConfigException, IncompatibleDatabaseVersion, BadURLException, \
    NameConflictError, PlaylistDoesNotExistException, YtccException
from ytcc.printer import JSONPrinter, XSVPrinter, VideoPrintable, TablePrinter, \
    PlaylistPrintable, Printer
from ytcc.tui import print_meta, Interactive

T = TypeVar("T")  # pylint: disable=invalid-name
ytcc: core.Ytcc
printer: Printer
logger = logging.getLogger(__name__)


class CommaList(click.ParamType, Generic[T]):
    name = "comma_separated_values"

    def __init__(self, validator: Callable[[str], T]):
        self.validator = validator

    def convert(self, value, param, ctx) -> List[T]:
        try:
            return [self.validator(elem.strip()) for elem in value.split(",")]
        except ValueError:
            self.fail(f"Unexpected value {value} in comma separated list")


version_text = f"""%(prog)s, version %(version)s

Copyright (C) 2015-2020  {__author__}
This program comes with ABSOLUTELY NO WARRANTY; This is free software, and you
are welcome to redistribute it under certain conditions.  See the GNU General
Public Licence for details."""


@click.group()
@click.option("--conf", "-c", type=click.Path(file_okay=True, dir_okay=False),
              envvar="YTCC_CONFIG",
              help="Override configuration file.")
@click.option("--loglevel", "-l", type=click.Choice(["critical", "info", "debug"]), default="info",
              show_default=True,
              help="Set the log level. Overrides the log level configured in the config file.")
@click.option("--output", "-o", type=click.Choice(["json", "table", "xsv"]), default="table",
              show_default=True,
              help="Set output format. `json` prints in JSON format, which is usually not filtered"
                   " by --attribute options of commands. `table` prints a human readable table."
                   " `xsv` prints x-separated values, where x can be set with the -s option.")
@click.option("--separator", "-s", default=",", show_default=True,
              help="Set the delimiter used in XSV format.")
@click.version_option(version=__version__, prog_name="ytcc", message=version_text)
@click.pass_context
def cli(ctx: click.Context, conf: Path, loglevel: str, output: str, separator: str) -> None:
    """Ytcc - the (not only) YouTube channel checker.

    Ytcc "subscribes" to playlists (supported by youtube-dl) and tracks new videos published to
    those playlists.

    To show the detailed help of a COMMAND run `ytcc COMMAND --help`.
    """
    debug_format = "[%(created)f] [%(processName)s/%(threadName)s] " \
                   "%(name)s.%(levelname)s: %(message)s"
    log_format = "%(levelname)s: %(message)s"

    logging.basicConfig(
        level=loglevel.upper(),
        stream=sys.stderr,
        format=debug_format if loglevel == "debug" else log_format
    )
    try:
        if conf is None:
            config.load()
        else:
            config.load(str(conf))
    except BadConfigException as conf_exc:
        logger.error(str(conf_exc))
        ctx.exit(1)

    global ytcc, printer  # pylint: disable=global-statement,invalid-name

    ytcc = core.Ytcc()

    if output == "table":
        printer = TablePrinter()
    elif output == "json":
        printer = JSONPrinter()
    elif output == "xsv":
        printer = XSVPrinter(separator)


@cli.command()
@click.argument("name")
@click.argument("url")
@click.pass_context
def subscribe(ctx: click.Context, name: str, url: str):
    """Subscribe to a playlist.

    The NAME argument is the name used to refer to the playlist. The URL argument is the URL to a
    playlist that is supported by youtube-dl.
    """
    try:
        ytcc.add_playlist(name, url)
    except BadURLException:
        logger.error("The given URL does not point to a playlist or is not supported by "
                     "youtube-dl")
        ctx.exit(1)
    except NameConflictError:
        logger.error("The given name is already used for another playlist "
                     "or the playlist is already subscribed")
        ctx.exit(1)


@cli.command()
@click.argument("name")
@click.confirmation_option(
    prompt="Unsubscribing will remove videos from the database that are not part of another "
           "playlist. Do you really want to unsubscribe?"
)
@click.pass_context
def unsubscribe(ctx: click.Context, name: str):
    """Unsubscribe from a playlist.

    Unsubscribes from the playlist identified by NAME.
    """
    try:
        ytcc.delete_playlist(name)
    except PlaylistDoesNotExistException:
        logger.error("Playlist '%s' does not exist", name)
        ctx.exit(1)
    else:
        logger.info("Unsubscribed from %s", name)


@cli.command()
@click.argument("old")
@click.argument("new")
@click.pass_context
def rename(ctx: click.Context, old: str, new: str):
    """Rename a playlist.

    Renames the playlist OLD to NEW.
    """
    try:
        ytcc.rename_playlist(old, new)
    except NameConflictError as nce:
        logger.error("'%s'", str(nce))
        ctx.exit(1)


@cli.command()
@click.option("--attributes", "-a", type=CommaList(PlaylistAttr.from_str),
              help="Attributes of the playlist to be included in the output. "
                   f"Some of [{', '.join(map(lambda x: x.value, list(PlaylistAttr)))}].")
def subscriptions(attributes: List[PlaylistAttr]):
    """List all subscriptions."""
    if not filter:
        printer.filter = config.ytcc.playlist_attrs
    else:
        printer.filter = attributes
    printer.print(PlaylistPrintable(ytcc.list_playlists()))


@cli.command()
@click.argument("name")
@click.argument("tags", nargs=-1)
def tag(name: str, tags: Tuple[str, ...]):
    """Set tags of a playlist.

    Sets the TAGS associated with the playlist called NAME. If no tags are given, all tags are
    removed from the given playlist.
    """
    ytcc.tag_playlist(name, list(tags))


@cli.command()
@click.option("--max-fail", "-f", type=click.INT,
              help="Number of failed updates before a video is not checked for updates any more.")
@click.option("--max-backlog", "-b", type=click.INT,
              help="Number of videos in a playlist that are checked for updates.")
def update(max_fail: Optional[int], max_backlog: Optional[int]):
    """Check if new videos are available.

    Downloads metadata of new videos (if any) without playing or downloading the videos.
    """
    ytcc.update(max_fail, max_backlog)


common_list_options = [
    click.Option(["--tags", "-c"], type=CommaList(str),
                 help="Listed videos must be tagged with one of the given tags."),
    click.Option(["--since", "-s"], type=click.DateTime(["%Y-%m-%d"]),
                 default="1970-01-03",  # Minimum supported by .timestamp() on Windows
                 help="Listed videos must be published after the given date."),
    click.Option(["--till", "-t"], type=click.DateTime(["%Y-%m-%d"]),
                 default="3001-1-19",  # Maximum supported by .timestamp() on Windows (Y3K Bug)
                 help="Listed videos must be published before the given date."),
    click.Option(["--playlists", "-p"], type=CommaList(str),
                 help="Listed videos must be in on of the given playlists."),
    click.Option(["--ids", "-i"], type=CommaList(int),
                 help="Listed videos must have the given IDs."),
    click.Option(["--watched", "-w"], is_flag=True, default=False,
                 help="Listed videos include watched videos.")
]


def list_videos_impl(tags: List[str], since: datetime, till: datetime, playlists: List[str],
                     ids: List[int], attributes: List[str], watched: bool) -> None:
    ytcc.set_tags_filter(tags)
    ytcc.set_date_begin_filter(since)
    ytcc.set_date_end_filter(till)
    ytcc.set_playlist_filter(playlists)
    ytcc.set_video_id_filter(ids)
    ytcc.set_include_watched_filter(watched)
    if attributes:
        printer.filter = attributes
    else:
        printer.filter = config.ytcc.video_attrs
    printer.print(VideoPrintable(ytcc.list_videos()))


@cli.command("list")
@click.option("--attributes", "-a", type=CommaList(VideoAttr.from_str),
              help="Attributes of videos to be included in the output. "
                   f"Some of [{', '.join(map(lambda x: x.value, list(VideoAttr)))}].")
def list_videos(tags: List[str], since: datetime, till: datetime, playlists: List[str],
                ids: List[int], attributes: List[str], watched: bool):
    """List videos.

    Lists videos that match the given filter options. By default, all unwatched videos are listed.
    """
    list_videos_impl(tags, since, till, playlists, ids, attributes, watched)


@cli.command("ls")
def list_ids(tags: List[str], since: datetime, till: datetime, playlists: List[str],
             ids: List[int], watched: bool):
    """List IDs of unwatched videos in XSV format.

    Basically an alias for `ytcc --output xsv list --attributes id`. This alias can be useful for
    piping into the download, play, and mark commands. E.g: `ytcc ls | ytcc watch`
    """
    global printer  # pylint: disable=global-statement,invalid-name
    printer = XSVPrinter()
    list_videos_impl(tags, since, till, playlists, ids, ["id"], watched)


list_ids.params.extend(common_list_options)
list_videos.params.extend(common_list_options)


def _get_ids(ids: List[int]) -> Iterable[int]:
    if not ids and not sys.stdin.isatty():
        for line in sys.stdin:
            line = line.strip()
            try:
                yield int(line)
            except ValueError:
                logging.error("ID '%s' is not an integer", line)
                sys.exit(1)

    elif ids is not None:
        yield from ids


def _get_videos(ids: List[int]) -> Iterable[MappedVideo]:
    ids = list(_get_ids(ids))
    if ids:
        ytcc.set_video_id_filter(ids)
        ytcc.set_include_watched_filter(True)

    return ytcc.list_videos()


@cli.command()
@click.option("--audio-only", "-a", is_flag=True, default=False, help="Play only the audio track.")
@click.option("--no-meta", "-i", is_flag=True, default=False,
              help="Don't print video metadata and description.")
@click.option("--no-mark", "-m", is_flag=True, default=False,
              help="Don't mark the video as watched after playing it.")
@click.argument("ids", nargs=-1, type=click.INT)
def play(ids: Tuple[int, ...], audio_only: bool, no_meta: bool, no_mark: bool):
    """Play videos.

    Plays the videos identified by the given video IDs. If no IDs are given, ytcc tries to read IDs
    from stdin. If no IDs are given and no IDs were read from stdin, all unwatched videos are
    played.
    """
    videos = _get_videos(list(ids))

    loop_executed = False
    for video in videos:
        loop_executed = True
        if not no_meta:
            print_meta(video, sys.stderr)
        if ytcc.play_video(video, audio_only) and mark:
            ytcc.mark_watched(video)
        elif not no_mark:
            logger.warning("The video player terminated with an error. "
                           "The last video is not marked as watched!")

    if not loop_executed:
        logger.info("No videos to watch. No videos match the given criteria.")


@cli.command()
@click.argument("ids", nargs=-1, type=click.INT)
def mark(ids: Tuple[int, ...]):
    """Mark videos as watched.

    Marks videos as watched without playing or downloading them. If no IDs are given, ytcc tries to
    read IDs from stdin. If no IDs are given and no IDs were read from stdin, no videos are marked
    as watched.
    """
    processed_ids = list(_get_ids(list(ids)))
    if processed_ids:
        ytcc.mark_watched(processed_ids)


@cli.command()
@click.option("--path", "-p", type=click.Path(file_okay=False, dir_okay=True), default="",
              help="Set the download directory.")
@click.option("--audio-only", "-a", is_flag=True, default=False,
              help="Download only the audio track.")
@click.option("--no-mark", "-m", is_flag=True, default=False,
              help="Don't mark the video as watched after downloading it.")
@click.argument("ids", nargs=-1, type=click.INT)
def download(ids: Tuple[int, ...], path: Path, audio_only: bool, no_mark: bool):
    """Download videos.

    Downloads the videos identified by the given video IDs. If no IDs are given, ytcc tries to read
    IDs from stdin. If no IDs are given and no IDs were read from stdin, all unwatched videos are
    downloaded.
    """
    videos = _get_videos(list(ids))

    for video in videos:
        logger.info(
            "Downloading video '%s' from playlist(s) %s",
            video.title,
            ", ".join(f"'{pl.name}'" for pl in video.playlists)
        )
        if ytcc.download_video(video, str(path), audio_only) and not no_mark:
            ytcc.mark_watched(video)


@cli.command()
def tui():
    """Start an interactive terminal user interface."""
    Interactive(ytcc).run()


@cli.command()
@click.confirmation_option(
    prompt="Do you really want to remove all watched videos from the database?"
)
def cleanup():
    """Remove all watched videos from the database.

    WARNING!!! This removes all metadata of watched, marked as watched, and downloaded videos from
    ytcc's database. This cannot be undone! In most cases you won't need this command, but it is
    useful to keep the database size small.
    """
    ytcc.cleanup()


@cli.command("import")
@click.argument("file", nargs=1, type=click.Path(exists=True, file_okay=True, dir_okay=False))
def import_(file: Path):
    """Import YouTube subscriptions from OPML file.

    You can export your YouTube subscriptions at https://www.youtube.com/subscription_manager.
    """
    ytcc.import_yt_opml(file)


@cli.command()
def bug_report():
    """Show debug information for bug reports.

    Shows versions of dependencies and configuration relevant for any bug report. Please include
    the output of this command when filing a new bug report!
    """
    # pylint: disable=import-outside-toplevel
    import youtube_dl.version
    import subprocess
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
    try:
        subprocess.run(["mpv", "--version"], check=False)
    except FileNotFoundError:
        print("mpv is not installed")
    print()
    print("---config dump---")
    print(config.dumps())


def main():
    try:
        cli.main(standalone_mode=False)
    except DatabaseError as db_err:
        logger.error("Cannot connect to the database or query failed unexpectedly")
        logger.debug("Unknown database error", exc_info=db_err)
        sys.exit(1)
    except IncompatibleDatabaseVersion:
        logger.error("This version of ytcc is not compatible with the older database versions."
                     "See https://github.com/woefe/ytcc#migrating-from-version-1 for more "
                     "details.")
        sys.exit(1)
    except YtccException as exc:
        logger.error("%s", str(exc))
        logger.debug("Unknown ytcc exception", exc_info=exc)
        sys.exit(1)
    except click.exceptions.Exit as exc:
        sys.exit(exc.exit_code)
    except click.Abort:
        click.echo("Aborted!", file=sys.stderr)
        sys.exit(1)
    except click.ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
