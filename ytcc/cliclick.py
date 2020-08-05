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
from datetime import datetime
from typing import List, Any, Callable, TypeVar, Generic

import click

from ytcc import core

T = TypeVar("T")

ytcc = core.Ytcc()

class CommaList(click.ParamType, Generic[T]):

    def __init__(self, validator: Callable[[str], T]):
        self.validator = validator

    def convert(self, value, param, ctx) -> List[T]:
        try:
            return list(map(self.validator, value.partition(",")))
        except:
            self.fail(f"Unexpected value {value}")


@click.group()
@click.option("--config")
@click.option("--verbose")
def cli(config, verbose):
    pass


@cli.command()
@click.argument("name")
@click.argument("url")
def subscribe(name: str, url: str):
    ytcc.add_playlist(name, url)


@cli.command()
@click.argument("name")
def unsubscribe(name: str):
    ytcc.delete_playlist(name)


@cli.command()
@click.argument("old")
@click.argument("new")
def rename(old: str, new: str):
    ytcc.rename_playlist(old, new)


@cli.command()
@click.option("--show-tags")
def subscriptions():
    print(list(ytcc.list_playlists()))


@cli.command()
@click.argument("name")
@click.argument("tags", nargs=-1)
def tag(name: str, tags: List[str]):
    pass


@cli.command()
def update():
    ytcc.update()


@cli.command()
@click.option("--all", "-a")
@click.option("--tags")
@click.option("--since")
@click.option("--till")
@click.option("--channel")
@click.option("--ids", "-i")
@click.option("--attributes")
@click.option("--json")
@click.option("--separatedby")
def list(since: datetime, till: datetime, ids: List[int], all: bool, tags: List[str],
         attributes: List[str], separator: str, ):
    pass


@cli.command()
@click.argument("--ids", nargs=-1)
def play(ids: List[int]):
    pass


@cli.command()
@click.argument("--ids", nargs=-1)
def mark():
    pass


@cli.command()
@click.option("--path")
@click.argument("id", nargs=-1)
def download():
    pass


@cli.command()
def tui():
    pass


@cli.command()
def cleanup():
    ytcc.cleanup()


@cli.command()
def bug_report():
    pass


@cli.command()
def version():
    pass

if __name__ == '__main__':
    cli()
