# ytcc - The YouTube channel checker
# Copyright (C) 2021  Wolfgang Popp
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
from typing import List, Callable, TypeVar, Generic, Optional, Iterable, Tuple, Any, Union

import click
from click.exceptions import Exit

from ytcc import __version__, __author__
from ytcc import core, config
from ytcc.config import PlaylistAttr, VideoAttr, Direction
from ytcc.database import MappedVideo
from ytcc.exceptions import BadConfigException, IncompatibleDatabaseVersion, BadURLException, \
    NameConflictError, PlaylistDoesNotExistException, YtccException
from ytcc.printer import JSONPrinter, XSVPrinter, VideoPrintable, TablePrinter, \
    PlaylistPrintable, Printer, RSSPrinter
from ytcc.tui import print_meta, Interactive

T = TypeVar("T")  # pylint: disable=invalid-name
printer: Printer
logger = logging.getLogger(__name__)
pass_ytcc = click.make_pass_decorator(core.Ytcc)


class CommaList(click.ParamType, Generic[T]):
    name = "comma_separated_values"

    def __init__(self, validator: Callable[[str], T]):
        self.validator = validator

    def convert(self, value, param, ctx) -> List[T]:  # pylint: disable=inconsistent-return-statements
        try:
            return [self.validator(elem.strip()) for elem in value.split(",")]
        except ValueError:
            self.fail(f"Unexpected value {value} in comma separated list")


class TruncateVals(click.ParamType):
    name = "truncate"

    def convert(self, value, param, ctx) -> Union[None, str, int]:  # pylint: disable=inconsistent-return-statements
        if value == "max":
            return "max"
        if value == "no":
            return None
        try:
            return int(value)
        except ValueError:
            self.fail(f"Unexpected value {value}. Must be 'no', 'max', or an integer")


version_text = f"""%(prog)s, version %(version)s

Copyright (C) 2015-2021  {__author__}
This program comes with ABSOLUTELY NO WARRANTY; This is free software, and you
are welcome to redistribute it under certain conditions.  See the GNU General
Public Licence for details.

See `%(prog)s bug-report` for more detailed version information."""


def _load_completion_conf(args: List[str]) -> None:
    conf_path = None
    try:
        idx = args.index("--conf")
    except ValueError:
        pass
    else:
        if idx + 1 < len(args):
            conf_path = args[idx + 1]

    if conf_path:
        config.load(conf_path)
    else:
        config.load()


def ids_completion(watched: bool = False):
    def complete(ctx: Any, args: List[str],  # pylint: disable=unused-argument
                 incomplete: str) -> List[Union[str, Tuple[str, str]]]:
        try:
            _load_completion_conf(args)
        except BadConfigException:
            return []

        with core.Ytcc() as ytcc:
            ytcc.set_watched_filter(watched)
            return [
                (v_id, title)
                for v_id, title in map(lambda v: (str(v.id), v.title), ytcc.list_videos())
                if v_id.startswith(incomplete)
            ]

    return complete


def playlist_completion(ctx: Any, args: List[str],  # pylint: disable=unused-argument
                        incomplete: str) -> List[Union[str, Tuple[str, str]]]:
    try:
        _load_completion_conf(args)
    except BadConfigException:
        return []

    with core.Ytcc() as ytcc:
        return [
            playlist.name
            for playlist in ytcc.list_playlists()
            if incomplete.lower() in playlist.name.lower()
        ]


def tag_completion(ctx: Any, args: List[str],  # pylint: disable=unused-argument
                   incomplete: str) -> List[Union[str, Tuple[str, str]]]:
    try:
        _load_completion_conf(args)
    except BadConfigException:
        return []

    with core.Ytcc() as ytcc:
        return [tag for tag in ytcc.list_tags() if incomplete.lower() in tag.lower()]


@click.group()
@click.option("--conf", "-c", type=click.Path(file_okay=True, dir_okay=False),
              envvar="YTCC_CONFIG",
              help="Override configuration file.")
@click.option("--loglevel", "-l", type=click.Choice(["critical", "info", "debug"]), default="info",
              show_default=True,
              help="Set the log level. Overrides the log level configured in the config file.")
@click.option("--output", "-o", type=click.Choice(["json", "table", "xsv", "rss"]),
              default="table", show_default=True,
              help="Set output format. `json` prints in JSON format, which is usually not filtered"
                   " by --attribute options of commands. `table` prints a human readable table."
                   " `xsv` prints x-separated values, where x can be set with the -s option."
                   " `rss` prints a RSS 2.0 feed of videos.")
@click.option("--separator", "-s", default=",", show_default=True,
              help="Set the delimiter used in XSV format.")
@click.option("--truncate", "-t", default="max", show_default=True, type=TruncateVals(),
              help="Truncate the table output. 'max' truncates to terminal width, 'no' disables"
                   " truncating, an integer N truncates to length N.")
@click.version_option(version=__version__, prog_name="ytcc", message=version_text)
@click.pass_context
def cli(ctx: click.Context, conf: Path, loglevel: str, output: str, separator: str,
        truncate: Union[None, str, int]) -> None:
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

    global printer  # pylint: disable=global-statement,invalid-name

    ytcc = ctx.ensure_object(core.Ytcc)
    ctx.call_on_close(ytcc.close)

    if output == "table":
        printer = TablePrinter(truncate)
    elif output == "json":
        printer = JSONPrinter()
    elif output == "xsv":
        printer = XSVPrinter(separator)
    elif output == "rss":
        printer = RSSPrinter()


@cli.command()
@click.argument("name")
@click.argument("url")
@click.option("--reverse", is_flag=True, default=False,
              help="Check the playlist in reverse order. This should be used for playlists where "
                   "the latest videos are added to the end of the playlist. WARNING: Using this "
                   "option on large playlists slows down updating!")
@pass_ytcc
def subscribe(ytcc: core.Ytcc, name: str, url: str, reverse: bool):
    """Subscribe to a playlist.

    The NAME argument is the name used to refer to the playlist. The URL argument is the URL to a
    playlist that is supported by youtube-dl.
    """
    try:
        ytcc.add_playlist(name, url, reverse)
    except BadURLException as bad_url:
        logger.error("The given URL does not point to a playlist or is not supported by "
                     "youtube-dl")
        raise Exit(1) from bad_url
    except NameConflictError as name_conflict:
        logger.error("The given name is already used for another playlist "
                     "or the playlist is already subscribed")
        raise Exit(1) from name_conflict


@cli.command()
@click.argument("name", autocompletion=playlist_completion)
@click.confirmation_option(
    prompt="Unsubscribing will remove videos from the database that are not part of another "
           "playlist. Do you really want to unsubscribe?"
)
@pass_ytcc
def unsubscribe(ytcc: core.Ytcc, name: str):
    """Unsubscribe from a playlist.

    Unsubscribes from the playlist identified by NAME.
    """
    try:
        ytcc.delete_playlist(name)
    except PlaylistDoesNotExistException as err:
        logger.error("Playlist '%s' does not exist", name)
        raise Exit(1) from err
    else:
        logger.info("Unsubscribed from %s", name)


@cli.command()
@click.argument("old", autocompletion=playlist_completion)
@click.argument("new")
@pass_ytcc
def rename(ytcc: core.Ytcc, old: str, new: str):
    """Rename a playlist.

    Renames the playlist OLD to NEW.
    """
    try:
        ytcc.rename_playlist(old, new)
    except NameConflictError as nce:
        logger.error("%s", str(nce))
        raise Exit(1) from nce


@cli.command("reverse")
@click.argument("playlists", nargs=-1, autocompletion=playlist_completion)
@pass_ytcc
def reverse_playlist(ytcc: core.Ytcc, playlists: Tuple[str, ...]):
    """Toggle the update behavior of playlists.

    Playlists updated in reverse might lead to slow updates with the `update` command.
    """
    for playlist in playlists:
        try:
            ytcc.reverse_playlist(playlist)
        except PlaylistDoesNotExistException as err:
            logger.error("Could not reverse playlist '%s', because it doesn't exist", playlist)
            raise Exit(1) from err
        else:
            logger.info("Reversed playlist '%s'", playlist)


@cli.command()
@click.option("--attributes", "-a", type=CommaList(PlaylistAttr.from_str),
              help="Attributes of the playlist to be included in the output. "
                   f"Some of [{', '.join(map(lambda x: x.value, list(PlaylistAttr)))}].")
@pass_ytcc
def subscriptions(ytcc: core.Ytcc, attributes: List[PlaylistAttr]):
    """List all subscriptions."""
    if not attributes:
        printer.filter = config.ytcc.playlist_attrs
    else:
        printer.filter = attributes
    printer.print(PlaylistPrintable(ytcc.list_playlists()))


@cli.command()
@click.argument("name", autocompletion=playlist_completion)
@click.argument("tags", nargs=-1, autocompletion=tag_completion)
@pass_ytcc
def tag(ytcc: core.Ytcc, name: str, tags: Tuple[str, ...]):
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
@pass_ytcc
def update(ytcc: core.Ytcc, max_fail: Optional[int], max_backlog: Optional[int]):
    """Check if new videos are available.

    Downloads metadata of new videos (if any) without playing or downloading the videos.
    """
    ytcc.update(max_fail, max_backlog)


_video_attrs = click.Choice(list(VideoAttr))
_video_attrs.name = "attribute"
_dir = click.Choice(list(Direction))
_dir.name = "direction"
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
                 help="Only watched videos are listed."),
    click.Option(["--unwatched", "-u"], is_flag=True, default=False,
                 help="Only unwatched videos are listed."),
    click.Option(["--order-by", "-o"], type=(_video_attrs, _dir), multiple=True,
                 help="Set the column and direction to sort listed videos. "
                      f"ATTRIBUTE is one of [{', '.join(VideoAttr)}]. "
                      f"Direction is one of [{', '.join(Direction)}].")

]


def apply_filters(ytcc: core.Ytcc, tags: List[str], since: datetime, till: datetime,
                  playlists: List[str], ids: List[int], watched: bool, unwatched: bool) -> None:
    if watched and unwatched:
        watched_filter = None
    elif watched and not unwatched:
        watched_filter = True
    else:
        watched_filter = False

    ytcc.set_tags_filter(tags)
    ytcc.set_date_begin_filter(since)
    ytcc.set_date_end_filter(till)
    ytcc.set_playlist_filter(playlists)
    ytcc.set_video_id_filter(ids)
    ytcc.set_watched_filter(watched_filter)


# pylint: disable=too-many-arguments
def list_videos_impl(ytcc: core.Ytcc, tags: List[str], since: datetime, till: datetime,
                     playlists: List[str], ids: List[int], attributes: List[str],
                     watched: bool, unwatched: bool,
                     order_by: Optional[List[Tuple[VideoAttr, Direction]]]) -> None:
    apply_filters(ytcc, tags, since, till, playlists, ids, watched, unwatched)
    if attributes:
        printer.filter = attributes
    else:
        printer.filter = config.ytcc.video_attrs
    if order_by is not None:
        ytcc.set_listing_order(order_by)
    printer.print(VideoPrintable(ytcc.list_videos()))


@cli.command("list")
@click.option("--attributes", "-a", type=CommaList(VideoAttr.from_str),
              help="Attributes of videos to be included in the output. "
                   f"Some of [{', '.join(VideoAttr)}].")
@pass_ytcc
def list_videos(ytcc: core.Ytcc, tags: List[str], since: datetime, till: datetime,
                playlists: List[str], ids: List[int], attributes: List[str],
                watched: bool, unwatched: bool,
                order_by: Optional[List[Tuple[VideoAttr, Direction]]]):
    """List videos.

    Lists videos that match the given filter options. By default, all unwatched videos are listed.
    """
    list_videos_impl(ytcc, tags, since, till, playlists, ids, attributes, watched, unwatched,
                     order_by)


@cli.command("ls")
@pass_ytcc
def list_ids(ytcc: core.Ytcc, tags: List[str], since: datetime, till: datetime,
             playlists: List[str], ids: List[int], watched: bool, unwatched: bool,
             order_by: Optional[List[Tuple[VideoAttr, Direction]]]):
    """List IDs of unwatched videos in XSV format.

    Basically an alias for `ytcc --output xsv list --attributes id`. This alias can be useful for
    piping into the download, play, and mark commands. E.g: `ytcc ls | ytcc watch`
    """
    global printer  # pylint: disable=global-statement,invalid-name
    printer = XSVPrinter()
    list_videos_impl(ytcc, tags, since, till, playlists, ids, ["id"], watched, unwatched, order_by)


@cli.command()
@pass_ytcc
def tui(ytcc: core.Ytcc, tags: List[str], since: datetime, till: datetime, playlists: List[str],
        ids: List[int], watched: bool, unwatched,
        order_by: Optional[List[Tuple[VideoAttr, Direction]]]):
    """Start an interactive terminal user interface."""
    apply_filters(ytcc, tags, since, till, playlists, ids, watched, unwatched)
    if order_by is not None:
        ytcc.set_listing_order(order_by)
    Interactive(ytcc).run()


list_ids.params.extend(common_list_options)
list_videos.params.extend(common_list_options)
tui.params.extend(common_list_options)


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


def _get_videos(ytcc: core.Ytcc, ids: List[int]) -> Iterable[MappedVideo]:
    ids = list(_get_ids(ids))
    if ids:
        ytcc.set_video_id_filter(ids)
        ytcc.set_watched_filter(None)

    return ytcc.list_videos()


@cli.command()
@click.option("--audio-only", "-a", is_flag=True, default=False, help="Play only the audio track.")
@click.option("--no-meta", "-i", is_flag=True, default=False,
              help="Don't print video metadata and description.")
@click.option("--no-mark", "-m", is_flag=True, default=False,
              help="Don't mark the video as watched after playing it.")
@click.argument("ids", nargs=-1, type=click.INT, autocompletion=ids_completion())
@pass_ytcc
def play(ytcc: core.Ytcc, ids: Tuple[int, ...], audio_only: bool, no_meta: bool, no_mark: bool):
    """Play videos.

    Plays the videos identified by the given video IDs. If no IDs are given, ytcc tries to read IDs
    from stdin. If no IDs are given and no IDs were read from stdin, all unwatched videos are
    played.
    """
    videos = _get_videos(ytcc, list(ids))

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
@click.argument("ids", nargs=-1, type=click.INT, autocompletion=ids_completion())
@pass_ytcc
def mark(ytcc: core.Ytcc, ids: Tuple[int, ...]):
    """Mark videos as watched.

    Marks videos as watched without playing or downloading them. If no IDs are given, ytcc tries to
    read IDs from stdin. If no IDs are given and no IDs were read from stdin, no videos are marked
    as watched.
    """
    processed_ids = list(_get_ids(list(ids)))
    if processed_ids:
        ytcc.mark_watched(processed_ids)


@cli.command()
@click.argument("ids", nargs=-1, type=click.INT, autocompletion=ids_completion(True))
@pass_ytcc
def unmark(ytcc: core.Ytcc, ids: Tuple[int, ...]):
    """Mark videos as unwatched.

    Marks videos as unwatched. If no IDs are given, ytcc tries to read IDs from stdin. If no IDs
    are given and no IDs were read from stdin, no videos are marked as watched.
    """
    processed_ids = list(_get_ids(list(ids)))
    if processed_ids:
        ytcc.mark_unwatched(processed_ids)


@cli.command()
@click.option("--path", "-p", type=click.Path(file_okay=False, dir_okay=True), default="",
              help="Set the download directory.")
@click.option("--audio-only", "-a", is_flag=True, default=False,
              help="Download only the audio track.")
@click.option("--no-mark", "-m", is_flag=True, default=False,
              help="Don't mark the video as watched after downloading it.")
@click.argument("ids", nargs=-1, type=click.INT, autocompletion=ids_completion())
@pass_ytcc
def download(ytcc: core.Ytcc, ids: Tuple[int, ...], path: Path, audio_only: bool, no_mark: bool):
    """Download videos.

    Downloads the videos identified by the given video IDs. If no IDs are given, ytcc tries to read
    IDs from stdin. If no IDs are given and no IDs were read from stdin, all unwatched videos are
    downloaded.
    """
    videos = _get_videos(ytcc, list(ids))

    for video in videos:
        logger.info(
            "Downloading video '%s' from playlist(s) %s",
            video.title,
            ", ".join(f"'{pl.name}'" for pl in video.playlists)
        )
        if ytcc.download_video(video, str(path), audio_only) and not no_mark:
            ytcc.mark_watched(video)


@cli.command()
@click.option("--keep", "-k", type=click.INT,
              help="Number of videos to keep. Defaults to the max_update_backlog setting.")
@click.confirmation_option(
    prompt="Do you really want to remove watched videos from the database?"
)
@pass_ytcc
def cleanup(ytcc: core.Ytcc, keep: Optional[int]):
    """Remove all watched videos from the database.

    WARNING!!! This removes all metadata of watched, marked as watched, and downloaded videos from
    ytcc's database. This cannot be undone! In most cases you won't need this command, but it is
    useful to keep the database size small.
    """
    if keep is None:
        keep = config.ytcc.max_update_backlog
    ytcc.cleanup(keep)


@cli.command("import")
@click.option("--format", "-f", type=click.Choice(["opml", "csv"]), default="csv",
              show_default=True, help="Format of the file to import.")
@click.argument("file", nargs=1, type=click.Path(exists=True, file_okay=True, dir_okay=False))
@pass_ytcc
def import_(ytcc: core.Ytcc, format: str, file: Path):  # pylint: disable=redefined-builtin
    """Import YouTube subscriptions from an OPML or CSV file.

    The CSV file must have three columns in following order: Channel ID, Channel URL, Channel name.

    You can export your YouTube subscriptions at https://takeout.google.com. In the takeout you
    find a CSV file with your subscriptions. To speed up the takeout export only your
    subscriptions, not your videos, comments, etc.

    The OPML export was available on YouTube some time ago and old versions of ytcc were also able
    to export subscriptions in the OPML format.
    """
    if format == "opml":
        ytcc.import_yt_opml(file)
    elif format == "csv":
        ytcc.import_yt_csv(file)


@cli.command()
def bug_report():
    """Show debug information for bug reports.

    Shows versions of dependencies and configuration relevant for any bug report. Please include
    the output of this command when filing a new bug report!
    """
    # pylint: disable=import-outside-toplevel
    import youtube_dl.version
    import subprocess
    import sqlite3
    print("---ytcc version---")
    print(__version__)
    print()
    print("---youtube-dl version---")
    print(youtube_dl.version.__version__)
    print()
    print("---SQLite version---")
    print("SQLite system library version:", sqlite3.sqlite_version)
    print("Python module version:", sqlite3.version)
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
        exit_code = cli.main(standalone_mode=False)
        sys.exit(exit_code)
    except DatabaseError as db_err:
        logger.error("Cannot connect to the database or query failed unexpectedly")
        logger.debug("Unknown database error", exc_info=db_err)
        sys.exit(1)
    except IncompatibleDatabaseVersion:
        logger.error("This version of ytcc is not compatible with the older database versions. "
                     "See https://github.com/woefe/ytcc/blob/master/doc/migrate.md for more "
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
