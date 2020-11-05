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
from datetime import datetime
from typing import List, Iterable, Dict, Any, NamedTuple, Optional

from wcwidth import wcswidth

from ytcc import config
from ytcc.database import MappedVideo, MappedPlaylist
from ytcc.exceptions import YtccException
from ytcc.terminal import printt


class Table(NamedTuple):
    header: List[str]
    data: List[List[str]]

    def apply_filter(self, column_names: List[str]) -> "Table":
        """
        Apply a column to the dataframe.

        Args:
            self: (todo): write your description
            column_names: (list): write your description
        """
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
        """
        Returns the table.

        Args:
            self: (todo): write your description
        """
        pass


class DictData(ABC):
    @abstractmethod
    def data(self) -> Iterable[Dict[str, Any]]:
        """
        Returns the data.

        Args:
            self: (todo): write your description
        """
        pass


class Printable(DictData, TableData, metaclass=ABCMeta):
    pass


class VideoPrintable(Printable):

    def __init__(self, videos: Iterable[MappedVideo]):
        """
        Initialize a list of videos.

        Args:
            self: (todo): write your description
            videos: (int): write your description
        """
        self.videos = videos

    @staticmethod
    def _format_duration(duration: float) -> str:
        """
        Format the duration.

        Args:
            duration: (float): write your description
        """
        return f"{duration // 60: 4.0f}:{duration % 60:02.0f}"

    @staticmethod
    def _format_publish_date(timestamp: float) -> str:
        """
        Format a date.

        Args:
            timestamp: (int): write your description
        """
        return datetime.fromtimestamp(timestamp).strftime(config.ytcc.date_format)

    def data(self) -> Iterable[Dict[str, Any]]:
        """
        Yield video data.

        Args:
            self: (todo): write your description
        """
        for video in self.videos:
            video_dict = asdict(video)
            video_dict["duration"] = self._format_duration(video.duration)
            video_dict["publish_date"] = self._format_publish_date(video.publish_date)
            yield video_dict

    def table(self) -> Table:
        """
        Return a list.

        Args:
            self: (todo): write your description
        """
        header = ["id", "url", "title", "description", "publish_date", "watched", "duration",
                  "extractor_hash", "playlists"]

        data = []
        for video in self.videos:
            data.append([
                str(video.id),
                video.url,
                video.title,
                video.description,
                self._format_publish_date(video.publish_date),
                str(video.watched),
                self._format_duration(video.duration),
                video.extractor_hash,
                ", ".join(map(lambda v: v.name, video.playlists))
            ])

        return Table(header, data)


class PlaylistPrintable(Printable):

    def __init__(self, playlists: Iterable[MappedPlaylist]):
        """
        Add a playlist.

        Args:
            self: (todo): write your description
            playlists: (todo): write your description
        """
        self.playlists = playlists

    def data(self) -> Iterable[Dict[str, Any]]:
        """
        Return a generator of playlists.

        Args:
            self: (todo): write your description
        """
        for playlist in self.playlists:
            yield asdict(playlist)

    def table(self) -> Table:
        """
        Returns a table of playlist.

        Args:
            self: (todo): write your description
        """
        header = ["name", "url", "tags"]
        data = []
        for playlist in self.playlists:
            data.append([playlist.name, playlist.url, ", ".join(playlist.tags)])

        return Table(header, data)


class Printer(ABC):

    def __init__(self):
        """
        Initialize the filter.

        Args:
            self: (todo): write your description
        """
        self._filter: Optional[List[Any]] = None

    @property
    def filter(self) -> Optional[List[Any]]:
        """
        Returns a filter.

        Args:
            self: (todo): write your description
        """
        return self._filter

    @filter.setter
    def filter(self, fields: List[Any]):
        """
        Filter the list of fields.

        Args:
            self: (todo): write your description
            fields: (list): write your description
        """
        self._filter = fields

    @abstractmethod
    def print(self, obj: Printable) -> None:
        """
        Print the given object

        Args:
            self: (todo): write your description
            obj: (todo): write your description
        """
        pass


class TablePrinter(Printer):

    def print(self, obj: TableData) -> None:
        """
        Prints the table.

        Args:
            self: (todo): write your description
            obj: (todo): write your description
        """
        table = obj.table()
        if self.filter is not None:
            table = table.apply_filter(self.filter)

        self.table_print(table)

    @staticmethod
    def print_col(text: str, width: int, background: Optional[int], bold: bool):
        """
        Print text to terminal.

        Args:
            text: (str): write your description
            width: (int): write your description
            background: (bool): write your description
            bold: (todo): write your description
        """
        padding = " " * max(0, (width - wcswidth(text)))
        padded = text + padding
        printt(" " + padded + " ", background=background, bold=bold)

    @staticmethod
    def print_row(columns: List[str], widths: List[int],
                  bold: bool = False, background: Optional[int] = None) -> None:
        """
        Prints a formatted ascii.

        Args:
            columns: (list): write your description
            widths: (int): write your description
            bold: (str): write your description
            background: (todo): write your description
        """

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
        """
        Print a table.

        Args:
            table: (str): write your description
        """
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
        """
        Initialize separator

        Args:
            self: (todo): write your description
            separator: (str): write your description
        """
        super().__init__()
        if len(separator) != 1:
            raise YtccException("Separator must be a single character")
        self.separator = separator

    def escape(self, string: str) -> str:
        """
        Escape the given string.

        Args:
            self: (todo): write your description
            string: (str): write your description
        """
        string = string.replace("\\", "\\\\")
        return string.replace(self.separator, "\\" + self.separator)

    def print(self, obj: TableData) -> None:
        """
        Print a table.

        Args:
            self: (todo): write your description
            obj: (todo): write your description
        """
        table = obj.table()
        if self.filter is not None:
            table = table.apply_filter(self.filter)

        for row in table.data:
            line = self.separator.join(self.escape(cell) for cell in row)
            print(line)


class JSONPrinter(Printer):

    def print(self, obj: DictData) -> None:
        """
        Prints the given object to stdout.

        Args:
            self: (todo): write your description
            obj: (todo): write your description
        """
        json.dump(list(obj.data()), sys.stdout, indent=2)
