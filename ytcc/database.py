# ytcc - The YouTube channel checker
# Copyright (C) 2019  Wolfgang Popp
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

from pathlib import Path
from typing import List, Iterable, Any, Dict

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class Channel(Base):
    __tablename__ = "channel"
    id = Column(Integer, primary_key=True)
    displayname = Column(String, unique=True)
    yt_channelid = Column(String, unique=True)

    videos = relationship("Video", back_populates="channel",
                          cascade="all, delete, delete-orphan")


class Video(Base):
    __tablename__ = "video"

    id = Column(Integer, primary_key=True)
    yt_videoid = Column(String, unique=True)
    title = Column(String)
    description = Column(String)
    publisher = Column(String, ForeignKey("channel.yt_channelid"))
    publish_date = Column(Float)
    watched = Column(Boolean)

    channel = relationship("Channel", back_populates="videos")


class Database:
    def __init__(self, path: str = ":memory:"):
        if path != ":memory:":
            expanded_path = Path(path).expanduser()
            expanded_path.parent.mkdir(parents=True, exist_ok=True)
            path = str(expanded_path)

        self.engine = create_engine(f"sqlite:///{path}")
        session = sessionmaker(bind=self.engine)
        self.session = session()
        Base.metadata.create_all(self.engine)

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        self.close()

    def close(self) -> None:
        self.session.commit()
        self.session.close()

    def add_channels(self, channels: Iterable[Channel]) -> None:
        self.session.add_all(channels)
        self.session.commit()

    def add_channel(self, channel: Channel) -> None:
        self.session.add(channel)
        self.session.commit()

    def get_channels(self) -> List[Channel]:
        return self.session.query(Channel).order_by(Channel.displayname).all()

    def delete_channels(self, display_names: Iterable[str]):
        channels = self.session.query(Channel).filter(Channel.displayname.in_(display_names))
        for channel in channels:
            self.session.delete(channel)
        self.session.commit()

    def add_videos(self, videos: Iterable[Dict[str, Any]]) -> None:
        videos = list(videos)
        query = Video.__table__.insert().prefix_with("OR IGNORE")
        self.session.commit()
        self.engine.execute(query, videos)
        self.session.commit()

    def resolve_video_ids(self, video_ids: Iterable[int]):
        return self.session.query(Video).filter(Video.id.in_(video_ids))

    def resolve_video_id(self, video_id: int) -> Video:
        return self.session.query(Video).get(video_id)

    def cleanup(self) -> None:
        """Delete all videos from all channels, but keeps the 30 latest videos of every channel."""
        sql = """
            delete from video
            where id in (
                select v.id
                from video v, channel c
                where v.publisher = c.yt_channelid and c.displayname = :displayname
                    and v.publish_date <= (
                        select v.publish_date
                        from video v, channel chan
                        where v.publisher = chan.yt_channelid and chan.displayname = c.displayname
                        order by v.publish_date desc
                        limit 30,1
                    )
            )
            """
        self.session.commit()
        self.engine.execute(sql, [{"displayname": e.displayname} for e in self.get_channels()])

        # Delete videos without channels.
        # This happend in older versions, because foreign keys were not enabled.
        # Also happens if foreign keys cannot be enabled due to missing compile flags.
        delete_dangling_sql = """
            delete
            from video
            where id in (
              select v.id
              from video v
                     left join channel c on v.publisher = c.yt_channelid
              where c.yt_channelid is null
            );
        """
        self.engine.execute(delete_dangling_sql)

        # Delete old full text search tables and triggers
        self.engine.execute("drop table if exists user_search;")
        self.engine.execute("drop trigger if exists populate_search;")
        self.engine.execute("drop trigger if exists delete_from_search;")

        self.engine.execute("vacuum;")
        self.session.commit()
