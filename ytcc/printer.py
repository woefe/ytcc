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

import json
import sys
from abc import ABC, abstractmethod, ABCMeta
from dataclasses import asdict
from datetime import datetime, timezone
from typing import List, Iterable, Dict, Any, NamedTuple, Optional

from wcwidth import wcswidth

try:
    import PyRSS2Gen as RSS2
except ImportError:
    RSS2 = None

from ytcc import config
from ytcc.database import MappedVideo, MappedPlaylist
from ytcc.exceptions import YtccException
from ytcc.terminal import printt


class Table(NamedTuple):
    header: List[str]
    data: List[List[str]]

    def apply_filter(self, column_names: List[str]) -> "Table":
        try:
            indices = [self.header.index(col) for col in column_names]
        except ValueError as index_err:
            raise ValueError("Invalid filter") from index_err
        else:
            filtered_header = [self.header[i] for i in indices]
            filtered_data = [
                [row[i] for i in indices]
                for row in self.data
            ]
            return Table(filtered_header, filtered_data)


class TableData(ABC):
    @abstractmethod
    def table(self) -> Table:
        pass


class DictData(ABC):
    @abstractmethod
    def data(self) -> Iterable[Dict[str, Any]]:
        pass


class Printable(DictData, TableData, metaclass=ABCMeta):
    pass


class VideoPrintable(Printable):

    def __init__(self, videos: Iterable[MappedVideo]):
        self.videos = videos

    @staticmethod
    def _format_duration(duration: float) -> str:
        return f"{duration // 60: 4.0f}:{duration % 60:02.0f}"

    @staticmethod
    def _format_date(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).strftime(config.ytcc.date_format)

    def data(self) -> Iterable[Dict[str, Any]]:
        for video in self.videos:
            video_dict = asdict(video)
            video_dict["duration"] = self._format_duration(video.duration)
            video_dict["publish_date"] = self._format_date(video.publish_date)
            yield video_dict

    def table(self) -> Table:
        header = ["id", "url", "title", "description", "publish_date", "watched", "duration",
                  "extractor_hash", "playlists"]

        data = []
        for video in self.videos:
            data.append([
                str(video.id),
                video.url,
                video.title,
                video.description,
                self._format_date(video.publish_date),
                self._format_date(video.watch_date) if video.watch_date else "No",
                self._format_duration(video.duration),
                video.extractor_hash,
                ", ".join(map(lambda v: v.name, video.playlists))
            ])

        return Table(header, data)


class PlaylistPrintable(Printable):

    def __init__(self, playlists: Iterable[MappedPlaylist]):
        self.playlists = playlists

    def data(self) -> Iterable[Dict[str, Any]]:
        for playlist in self.playlists:
            yield asdict(playlist)

    def table(self) -> Table:
        header = ["name", "url", "tags"]
        data = []
        for playlist in self.playlists:
            data.append([playlist.name, playlist.url, ", ".join(playlist.tags)])

        return Table(header, data)


class Printer(ABC):

    def __init__(self):
        self._filter: Optional[List[Any]] = None

    @property
    def filter(self) -> Optional[List[Any]]:
        return self._filter

    @filter.setter
    def filter(self, fields: List[Any]):
        self._filter = fields

    @abstractmethod
    def print(self, obj: Printable) -> None:
        pass


class TablePrinter(Printer):

    def print(self, obj: TableData) -> None:
        table = obj.table()
        if self.filter is not None:
            table = table.apply_filter(self.filter)

        self.table_print(table)

    @staticmethod
    def print_col(text: str, width: int, background: Optional[int], bold: bool):
        padding = " " * max(0, (width - wcswidth(text)))
        padded = text + padding
        printt(" " + padded + " ", background=background, bold=bold)

    @staticmethod
    def print_row(columns: List[str], widths: List[int],
                  bold: bool = False, background: Optional[int] = None) -> None:

        if len(widths) != len(columns) and not columns:
            raise ValueError("For every column, a width must be specified, "
                             "and columns must not be empty")

        for column, width in zip(columns[:-1], widths[:-1]):
            TablePrinter.print_col(column, width, background, bold)
            printt("│", background=background, bold=False)

        TablePrinter.print_col(columns[-1], widths[-1], background, bold)
        print()

    @staticmethod
    def table_print(table: Table) -> None:
        transposed = zip(table.header, *table.data)
        col_widths = [max(map(wcswidth, column)) for column in transposed]

        TablePrinter.print_row(table.header, col_widths, bold=True)
        header_line = "┼".join("─" * (width + 2) for width in col_widths)
        print(header_line)

        for i, row in enumerate(table.data):
            background = None if i % 2 == 0 else config.theme.table_alternate_background
            TablePrinter.print_row(row, col_widths, background=background)


class XSVPrinter(Printer):

    def __init__(self, separator: str = ","):
        super().__init__()
        if len(separator) != 1:
            raise YtccException("Separator must be a single character")
        self.separator = separator

    def escape(self, string: str) -> str:
        string = string.replace("\\", "\\\\")
        return string.replace(self.separator, "\\" + self.separator)

    def print(self, obj: TableData) -> None:
        table = obj.table()
        if self.filter is not None:
            table = table.apply_filter(self.filter)

        for row in table.data:
            line = self.separator.join(self.escape(cell) for cell in row)
            print(line)


class JSONPrinter(Printer):

    def print(self, obj: DictData) -> None:
        json.dump(list(obj.data()), sys.stdout, indent=2)


class RSSPrinter(Printer):

    def __init__(self):
        if RSS2 is None:
            raise YtccException("RSS is only available with PyRSS2Gen."
                                " Please install it, e.g. with 'pip install PyRSS2Gen'")

    def print(self, obj: DictData) -> None:
        if getattr(obj, 'videos', None) is None:
            raise YtccException('RSS feed is only available with video lists')

        rss = RSS2.RSS2(
            title="YTCC feed",
            link="https://github.com/woefe/ytcc",
            description="Latest videos from your YTCC instance",
            lastBuildDate=datetime.now(tz=timezone.utc),
            items=[
                RSS2.RSSItem(
                    title=entry["title"],
                    link=entry["url"],
                    author=",".join(playlist["name"] for playlist in entry["playlists"]),
                    description=entry["description"],
                    guid=RSS2.Guid(str(entry["id"]), isPermaLink=False),
                    pubDate=datetime.strptime(entry["publish_date"], config.ytcc.date_format)
                )
                for entry in obj.data()
            ]
        )
        rss.write_xml(sys.stdout)
