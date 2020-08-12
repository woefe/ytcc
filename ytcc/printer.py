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
import operator
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict, fields
from datetime import datetime
from typing import List, Iterable, Optional, Dict, Union, Any, NamedTuple

from ytcc import config
from ytcc.database import Video, MappedVideo
from ytcc.terminal import printtln


class Table(NamedTuple):
    header: List[str]
    data: List[List[str]]


class Printable(ABC):

    @abstractmethod
    def data(self) -> Iterable[Dict[str, Any]]:
        pass

    @abstractmethod
    def table(self) -> Table:
        pass


class VideoPrintable(Printable):
    header = ["id", "url", "title", "description", "publish_date", "watched", "duration",
              "extractor_hash", "playlists"]

    def __init__(self, videos: Iterable[MappedVideo]):
        self.videos = videos

    def data(self) -> Iterable[Dict[str, Any]]:
        for video in self.videos:
            yield asdict(video)

    def table(self) -> Table:

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

        return Table(self.header, data)


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
    pass

    # def print(self, obj: Printable) -> None:
    #    pass

    # def table_print(self, header: List[str], table: List[List[str]]) -> None:
    #    transposed = zip(header, *table)
    #    col_widths = [max(map(len, column)) for column in transposed]
    #    table_format = "│".join(itertools.repeat(" {{:<{}}} ", len(header))).format(*col_widths)

    #    header_line = "┼".join("─" * (width + 2) for width in col_widths)
    #    printtln(table_format.format(*header), bold=True)
    #    print(header_line)

    #    for i, row in enumerate(table):
    #        background = None if i % 2 == 0 else config.color.table_alternate_background
    #        printtln(table_format.format(*row), background=background)

    # def print_videos(self, videos: Iterable[Video],
    #                 quickselect_column: Optional[Iterable[str]] = None) -> None:
    #    def row_filter(row: Iterable[str]) -> List[str]:
    #        return list(itertools.compress(row, COLUMN_FILTER))

    #    def video_to_list(video: Video) -> List[str]:
    #        timestamp = unpack_optional(video.publish_date, lambda: 0)
    #        return [
    #            str(video.id),
    #            datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M"),
    #            str(video.displayname),
    #            str(video.title),
    #            video.url
    #            _("Yes") if video.watched else _("No")
    #        ]

    #    def concat_row(tag: str, video: Video) -> List[str]:
    #        row = row_filter(video_to_list(video))
    #        row.insert(0, tag)
    #        return row

    #    if quickselect_column is None:
    #        table = [row_filter(video_to_list(v)) for v in videos]
    #        table_print(row_filter(TABLE_HEADER), table)
    #    else:
    #        table = [concat_row(k, v) for k, v in zip(quickselect_column, videos)]
    #        header = row_filter(TABLE_HEADER)
    #        header.insert(0, "TAG")
    #        table_print(header, table)


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
            indices = [table.header.index(col) for col in self.filter]
        else:
            indices = list(range(len(table.header)))

        for row in table.data:
            line = self.separator.join(self.escape(row[i]) for i in indices)
            print(line)


class JSONPrinter(Printer):

    def print(self, obj: Printable) -> None:
        json.dump(list(obj.data()), sys.stdout, indent=2)
