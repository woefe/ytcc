# ytcc - The YouTube channel checker
# Copyright (C) 2018  Wolfgang Popp
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


class Video:

    def __init__(self, id, yt_videoid, title, description, publish_date, channelname, watched):
        self.id = id
        self.yt_videoid = yt_videoid
        self.title = title
        self.description = description
        self.publish_date = publish_date
        self.channelname = channelname
        self.watched = bool(watched)

    def __eq__(self, other):
        return self.id == other.id and \
            self.yt_videoid == other.yt_videoid and \
            self.title == other.title and \
            self.description == other.description and \
            self.publish_date == other.publish_date and \
            self.channelname == other.channelname and \
            self.watched == other.watched
