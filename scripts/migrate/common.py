from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class ExportedVideo:
    url: str
    title: str
    description: str
    publish_date: float
    watched: bool
    pl_name: str
    extractor_hash: str

@dataclass(frozen=True)
class ExportedChannel:
    channelid: str
    name: str
