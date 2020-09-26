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

import pytest
from click.testing import CliRunner
from ytcc.cli import cli


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def test_bug_report_command(cli_runner: CliRunner):
    result = cli_runner.invoke(cli, "bug-report")
    assert result.exit_code == 0


def test_xsv_printer_option(cli_runner: CliRunner):
    result = cli_runner.invoke(cli, ["--output", "xsv", "--separator", "ab"])
    assert result.exit_code != 0
