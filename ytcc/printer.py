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
import itertools
import json
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import List, Iterable, Dict, Any, NamedTuple

from ytcc.database import MappedVideo, MappedPlaylist
from ytcc.terminal import printtln


class Table(NamedTuple):
    header: List[str]
    data: List[List[str]]

    def apply_filter(self, column_names=List[str]) -> "Table":
        compressor = [col in column_names for col in self.header]
        filtered_data = [list(itertools.compress(row, compressor)) for row in self.data]
        filtered_header = list(itertools.compress(self.header, compressor))
        return Table(filtered_header, filtered_data)


class Printable(ABC):

    @abstractmethod
    def data(self) -> Iterable[Dict[str, Any]]:
        pass

    @abstractmethod
    def table(self) -> Table:
        pass


class VideoPrintable(Printable):

    def __init__(self, videos: Iterable[MappedVideo]):
        self.videos = videos

    def data(self) -> Iterable[Dict[str, Any]]:
        for video in self.videos:
            yield asdict(video)

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
                str(video.publish_date),
                str(video.watched),
                str(video.duration),
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
        self._filter = None

    @property
    def filter(self):
        return self._filter

    @filter.setter
    def filter(self, fields: List[str]):
        self._filter = fields

    @abstractmethod
    def print(self, obj: Printable) -> None:
        pass


class TablePrinter(Printer):

    def print(self, obj: Printable) -> None:
        table = obj.table()
        if self.filter is not None:
            table = table.apply_filter(self.filter)

        self.table_print(table)

    def table_print(self, table: Table) -> None:
        transposed = zip(table.header, *table.data)
        col_widths = [max(map(len, column)) for column in transposed]
        table_format = "│".join(itertools.repeat(" {{:<{}}} ", len(table.header))).format(
            *col_widths)

        header_line = "┼".join("─" * (width + 2) for width in col_widths)
        printtln(table_format.format(*table.header), bold=True)
        print(header_line)

        for i, row in enumerate(table.data):
            background = None if i % 2 == 0 else 244  # config.color.table_alternate_background
            printtln(table_format.format(*row), background=background)


class XSVPrinter(Printer):

    def __init__(self, separator: str):
        super().__init__()
        self.separator = separator

    def escape(self, s: str) -> str:
        s = s.replace("\\", "\\\\")
        return s.replace(self.separator, "\\" + self.separator)

    def print(self, obj: Printable) -> None:
        table = obj.table()
        if self.filter is not None:
            indices = table.apply_filter(self.filter)

        for row in table.data:
            line = self.separator.join(row)
            print(line)


class JSONPrinter(Printer):

    def print(self, obj: Printable) -> None:
        json.dump(list(obj.data()), sys.stdout, indent=2)
