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
import contextlib
from tempfile import NamedTemporaryFile
from typing import Callable

import pytest
from click.testing import CliRunner, Result

from ytcc.cli import cli


@pytest.fixture
def cli_runner(monkeypatch) -> Callable[..., Result]:
    @contextlib.contextmanager
    def context():
        with NamedTemporaryFile() as db_file, NamedTemporaryFile("w") as conf_file:
            conf_file.write("[ytcc]\n")
            conf_file.write(f"db_path={db_file.name}\n")
            conf_file.write("download_dir=/tmp/ytcc\n")
            conf_file.flush()
            yield lambda *args: CliRunner().invoke(cli, ["--conf", conf_file.name, *args])

    return context


def test_bug_report_command(cli_runner):
    from ytcc import __version__
    with cli_runner() as runner:
        result = runner("bug-report")
        assert result.exit_code == 0
        assert result.stdout.startswith(f"---ytcc version---\n{__version__}")
        assert "download_dir = /tmp/ytcc" in result.stdout


def test_subscribe(cli_runner):
    with cli_runner() as runner:
        result = runner("subscribe", "WebDriver",
                        "https://www.youtube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw/videos")
        assert result.exit_code == 0
        result = runner("--output", "xsv", "subscriptions")
        assert "WebDriver" in result.stdout


def test_subscribe_duplicate(cli_runner):
    with cli_runner() as runner:
        result = runner("subscribe", "WebDriver",
                        "https://www.youtube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw/videos")
        assert result.exit_code == 0
        result = runner("subscribe", "WebDriver",
                        "https://www.youtube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw/videos")
        assert result.exit_code != 0


def test_unsubscribe(cli_runner):
    with cli_runner() as runner:
        result = runner("subscribe", "WebDriver",
                        "https://www.youtube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw/videos")
        assert result.exit_code == 0

        result = runner("unsubscribe", "--yes", "WebDriver")
        assert result.exit_code == 0

        result = runner("unsubscribe", "--yes", "WebDriver")
        assert result.exit_code != 0


def test_rename(cli_runner):
    with cli_runner() as runner:
        result = runner("subscribe", "WebDriver",
                        "https://www.youtube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw/videos")
        assert result.exit_code == 0

        result = runner("rename", "WebDriver", "WebDriverTorso")
        assert result.exit_code == 0

        result = runner("-o", "xsv", "subscriptions")
        assert "WebDriverTorso" in result.stdout

        result = runner("rename", "WebDriver", "WebDriverTorso")
        assert result.exit_code != 0


def test_update(cli_runner):
    with cli_runner() as runner:
        result = runner("subscribe", "WebDriver",
                        "https://www.youtube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw/videos")
        assert result.exit_code == 0

        result = runner("update", "--max-backlog", "20")
        assert result.exit_code == 0

        result = runner("--output", "xsv", "list")
        assert len(result.stdout.splitlines()) == 20


def test_download(cli_runner):
    with cli_runner() as runner:
        result = runner("subscribe", "WebDriver",
                        "https://www.youtube.com/channel/UCsLiV4WJfkTEHH0b9PmRklw/videos")
        assert result.exit_code == 0

        result = runner("update", "--max-backlog", "20")
        assert result.exit_code == 0

        result = runner("download", "1")
        assert result.exit_code == 0


def test_xsv_printer_option(cli_runner):
    with cli_runner() as runner:
        result = runner("--output", "xsv", "--separator", "ab")
        assert result.exit_code != 0
