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

import contextlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Callable

import pytest
from click.testing import CliRunner, Result

from test import WEBDRIVER_VIDEOS, WEBDRIVER_PLAYLIST
from ytcc import InvalidSubscriptionFileError


class YtccRunner(CliRunner):
    def __init__(self, conf_file, db_file, download_dir):
        super().__init__()
        self.conf_file = conf_file
        self.db_file = db_file
        self.download_dir = download_dir

    def __call__(self, *args, **kwargs):
        from ytcc.cli import cli

        if kwargs.get("subscribe", False):
            from ytcc.database import Database
            with Database(self.db_file) as db:
                db.add_playlist(WEBDRIVER_PLAYLIST.name, WEBDRIVER_PLAYLIST.url)
            del kwargs["subscribe"]

        if kwargs.get("update", False):
            from ytcc.database import Database
            with Database(self.db_file) as db:
                db.add_videos(WEBDRIVER_VIDEOS, WEBDRIVER_PLAYLIST)
            del kwargs["update"]

        return self.invoke(cli, ["--conf", self.conf_file, *args], **kwargs)


@pytest.fixture
def cli_runner() -> Callable[..., Result]:
    @contextlib.contextmanager
    def context() -> YtccRunner:
        with NamedTemporaryFile(delete=False) as db_file, \
                NamedTemporaryFile("w", delete=False) as conf_file, \
                TemporaryDirectory() as download_dir:
            conf_file.write("[ytcc]\n")
            conf_file.write(f"db_path={db_file.name}\n")
            conf_file.write(f"download_dir={download_dir}\n")

            db_file.close()
            conf_file.close()

            try:
                yield YtccRunner(conf_file.name, db_file.name, download_dir)
            finally:
                os.remove(conf_file.name)
                os.remove(db_file.name)

    return context


def test_bug_report_command(cli_runner):
    from ytcc import __version__
    with cli_runner() as runner:
        result = runner("bug-report")
        assert result.exit_code == 0
        assert result.stdout.startswith(f"---ytcc version---\n{__version__}")
        assert f"download_dir = {runner.download_dir}" in result.stdout
        assert f"db_path = {runner.db_file}" in result.stdout


def test_subscribe(cli_runner):
    with cli_runner() as runner:
        result = runner("subscribe", "WebDriver",
                        "https://www.youtube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw/videos")
        assert result.exit_code == 0
        result = runner("--output", "xsv", "subscriptions")
        assert "WebDriver" in result.stdout


def test_subscribe_duplicate(cli_runner):
    with cli_runner() as runner:
        result = runner(
            "subscribe", "WebDriver",
            "https://www.youtube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw/videos",
            subscribe=True
        )
        assert result.exit_code != 0


def test_subscribe_bad_url(cli_runner, caplog):
    with cli_runner() as runner:
        result = runner("subscribe", "Test", "test.kom")
        assert result.exit_code != 0
        msg = "The given URL does not point to a playlist or is not supported by youtube-dl"
        assert any(map(lambda r: r.msg == msg, caplog.records))


def test_unsubscribe(cli_runner):
    with cli_runner() as runner:
        result = runner("unsubscribe", "--yes", "WebDriver", subscribe=True)
        assert result.exit_code == 0

        result = runner("unsubscribe", "--yes", "WebDriver")
        assert result.exit_code != 0


def test_rename(cli_runner):
    with cli_runner() as runner:
        result = runner("rename", "WebDriver", "WebDriverTorso", subscribe=True)
        assert result.exit_code == 0

        result = runner("-o", "xsv", "subscriptions")
        assert "WebDriverTorso" in result.stdout

        result = runner("rename", "WebDriver", "WebDriverTorso")
        assert result.exit_code != 0


def test_import(cli_runner):
    with cli_runner() as runner:
        result = runner("import", "--format=opml", "test/data/subscriptions.small")
        assert result.exit_code == 0

        result = runner("subscriptions")
        assert "NoCopyrightSounds" in result.stdout
        assert "gotbletu" in result.stdout


def test_import_duplicate(cli_runner, caplog):
    with cli_runner() as runner:
        result = runner("import", "--format=opml", "test/data/subscriptions.duplicate")
        assert result.exit_code == 0
        assert caplog.records
        for record in caplog.records:
            if record.levelname == "WARNING":
                assert "already subscribed" in record.msg


def test_import_broken(cli_runner):
    with cli_runner() as runner:
        result = runner("import", "--format=opml", "test/data/subscriptions.broken")
        assert isinstance(result.exception, InvalidSubscriptionFileError)
        assert "not a valid YouTube export file" in str(result.exception)


def test_tag(cli_runner):
    with cli_runner() as runner:
        result = runner("tag", "WebDriver", "test1", subscribe=True)
        assert result.exit_code == 0

        result = runner("tag", "WebDriver", "test2", update=True)
        assert result.exit_code == 0

        result = runner("--output", "json", "list", "--tags", "test1,test2")
        assert len(json.loads(result.stdout)) == 20


def test_update(cli_runner, caplog):
    with cli_runner() as runner:
        result = runner("update", "--max-backlog", "20", subscribe=True)
        assert result.exit_code == 0

        errors = len([r for r in caplog.records if r.levelname == "ERROR"])
        result = runner("--output", "xsv", "list")
        assert len(result.stdout.splitlines()) + errors == 20
        assert errors < 5


def test_comma_list_error(cli_runner):
    with cli_runner() as runner:
        result = runner("list", "--ids", "a,b")
        assert result.exit_code != 0
        assert "Unexpected value" in result.stdout


def test_bad_id(cli_runner, caplog):
    with cli_runner() as runner:
        result = runner("play", input="a")
        assert result.exit_code != 0
        assert "is not an integer" in caplog.records[0].msg


def test_cleanup(cli_runner):
    with cli_runner() as runner:
        result = runner("mark", subscribe=True, update=True, input="19\n20")
        assert result.exit_code == 0

        result = runner("cleanup", "--keep", "18", input="y")
        assert result.exit_code == 0

        result = runner("ls", "--watched", "--unwatched")
        assert result.exit_code == 0
        outlines = result.stdout.splitlines()
        assert "19" not in outlines
        assert "20" not in outlines
        assert len(outlines) == 18


def test_download(cli_runner):
    with cli_runner() as runner:
        result = runner("download", "1", subscribe=True, update=True)
        assert result.exit_code == 0

        result = runner(
            "--output", "xsv",
            "list",
            "--attributes", "title",
            "--ids", "1",
            "--watched"
        )
        assert Path(runner.download_dir, result.stdout.splitlines()[0] + ".mkv").is_file()


def test_pipe_mark(cli_runner):
    with cli_runner() as runner:
        result = runner("ls", subscribe=True, update=True)
        result = runner("mark", input=result.stdout)
        assert result.exit_code == 0
        assert runner("ls").stdout == ""


def test_play_video(cli_runner):
    with cli_runner() as runner:
        result = runner("play", "1", subscribe=True, update=True)
        assert result.exit_code == 0

        result = runner("ls")
        assert len(result.stdout.splitlines()) == 19


def test_play_video_empty(cli_runner, caplog):
    with cli_runner() as runner:
        caplog.set_level("INFO")
        result = runner("play")
        rec = caplog.records[0]
        assert rec.levelname == "INFO"
        assert "No videos to watch" in rec.msg
        assert result.exit_code == 0


def test_no_command(cli_runner):
    with cli_runner() as runner:
        result = runner("--output", "xsv", "--separator", "ab")
        assert result.exit_code != 0
