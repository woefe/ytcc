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

import html
import json
import sys
import xml.etree.ElementTree as ET
from email.utils import format_datetime as rss2_date
from abc import ABC, abstractmethod, ABCMeta
from dataclasses import asdict
from datetime import datetime, timezone
from typing import List, Iterable, Dict, Any, NamedTuple, Optional, Union

from wcwidth import wcswidth

from ytcc import config
from ytcc.database import MappedVideo, MappedPlaylist
from ytcc.exceptions import YtccException
from ytcc.terminal import printt, get_terminal_width


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
        if not duration or duration < 0:
            return "   0:00"
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
                  "thumbnail_url", "extractor_hash", "playlists"]

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
                video.thumbnail_url or "",
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
        header = ["name", "url", "reverse", "tags"]
        data = []
        for playlist in self.playlists:
            is_reverse = str(playlist.reverse).lower()
            data.append([playlist.name, playlist.url, is_reverse, ", ".join(playlist.tags)])

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

    def __init__(self, truncate: Union[None, str, int] = "max"):
        """Initialize a new TablePrinter.

        :param truncate: Truncates row width. None to disable truncating, "max" to truncate to
                         terminal width, an integer n to truncate to length n.
        """
        super().__init__()
        self.truncate = truncate

    def print(self, obj: TableData) -> None:
        table = obj.table()
        if self.filter is not None:
            table = table.apply_filter(self.filter)

        self.table_print(table)

    @staticmethod
    def print_col(text: str, width: int, background: Optional[int], bold: bool):
        text = TablePrinter.wc_truncate(text, width)
        padding = " " * max(0, (width - wcswidth(text)))
        padded = text + padding
        printt(" " + padded + " ", background=background, bold=bold)

    @staticmethod
    def wc_truncate(text, max_len):
        if max_len < 1:
            raise ValueError("max_len must be greater or equal to 1")

        i = 0
        while wcswidth(text) > max_len > i:
            text = text[:max_len - i - 1] + "…"
            i = i + 1
        return text

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

    def table_print(self, table: Table) -> None:
        transposed = zip(table.header, *table.data)
        col_widths = [max(map(wcswidth, column)) for column in transposed]
        if self.truncate is not None:
            columns = dict(zip(table.header, enumerate(col_widths)))
            terminal_width = get_terminal_width() if self.truncate == "max" else int(self.truncate)
            min_col_widths = (
                ("duration", 7),
                ("publish_date", 10),
                ("playlists", 9),
                ("title", 21)
            )
            for column, min_col_width in min_col_widths:
                printed_table_width = sum(col_widths) + 3 * (len(col_widths) - 1) + 2
                index, col_width = columns.get(column, (-1, 0))
                if terminal_width < printed_table_width and index >= 0:
                    truncated_width = col_width - (printed_table_width - terminal_width)
                    col_widths[index] = max(min_col_width, truncated_width)

        self.print_row(table.header, col_widths, bold=True)
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
    def print(self, obj: Printable) -> None:
        if not isinstance(obj, VideoPrintable):
            raise YtccException("RSS can only be generated for videos")

        rss = ET.Element("rss", version="2.0")
        channel = ET.SubElement(rss, "channel")
        title = ET.SubElement(channel, "title")
        title.text = "Ytcc videos"
        link = ET.SubElement(channel, "link")
        link.text = "https://github.com/woefe/ytcc"
        description = ET.SubElement(channel, "description")
        description.text = "Latest videos from your ytcc subscriptions"
        last_build_date = ET.SubElement(channel, "lastBuildDate")
        last_build_date.text = rss2_date(datetime.now(tz=timezone.utc))

        for video in obj.videos:
            item = ET.SubElement(channel, "item")
            title = ET.SubElement(item, "title")
            title.text = video.title
            link = ET.SubElement(item, "link")
            link.text = video.url
            author = ET.SubElement(item, "author")
            author.text = ", ".join(map(lambda v: v.name, video.playlists))
            description = ET.SubElement(item, "description")
            description.text = f"<pre>{html.escape(video.description)}</pre>"
            pub_date = ET.SubElement(item, "pubDate")
            pub_date.text = rss2_date(datetime.fromtimestamp(video.publish_date))
            guid = ET.SubElement(item, "guid", isPermaLink="false")
            guid.text = f"ytcc::{video.id}::{video.extractor_hash}"

        ET.dump(rss)
