#!/usr/bin/env python3

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

from datetime import date

import click

from ytcc import __version__
from ytcc.cli import cli


class BlankUsageFormatter(click.HelpFormatter):
    def write_usage(self, prog, args="", prefix=""):
        super().write_usage(prog, args, prefix)


def main():
    ctx = cli.make_context("ytcc", [""])
    with open("doc/ytcc.1", "w", encoding="utf-8") as manpage:
        today = date.today().strftime("%b %Y")
        manpage.write(f'.TH ytcc 1 "{today}" "{__version__}" ')
        manpage.write('"ytcc manual"\n')
        manpage.write(".SH NAME\n")
        manpage.write(
            "ytcc - Command line tool to keep track of your favorite playlists on "
            "YouTube and many other places\n"
        )
        manpage.write(".SH SYNOPSIS\n")
        manpage.write("ytcc [OPTIONS...] COMMAND [ARGS...]\n")

        manpage.write(".SH DESCRIPTION\n")
        manpage.write("\n".join(map(str.strip, cli.__doc__.splitlines())))

        manpage.write("\n.SH OPTIONS\n")
        for param in cli.params:
            opts, help_text = param.get_help_record(ctx)
            manpage.write(f".SS {opts}\n")
            manpage.write(help_text)
            manpage.write("\n")
        help_opt = cli.get_help_option(ctx)
        manpage.write(".SS ")
        manpage.write(", ".join(help_opt.opts))
        manpage.write("\nShow help and exit.\n")

        manpage.write(".SH COMMANDS\n")

        for cmd in cli.commands.values():
            ctx = click.Context(cmd, info_name=cmd.name)
            formatter = BlankUsageFormatter()
            cmd.format_usage(ctx, formatter)
            manpage.write(f".SS {formatter.getvalue()}\n")
            manpage.write(cmd.help)
            manpage.write("\n.P\n")
            manpage.write(".B OPTIONS:\n")
            for param in cmd.params:
                if isinstance(param, click.Option):
                    opts, help_text = param.get_help_record(ctx)
                    manpage.write(".P\n")
                    manpage.write(f".B {opts}\n")
                    manpage.write(help_text)
                    manpage.write("\n")
            help_opt = cmd.get_help_option(ctx)
            manpage.write(".P\n")
            manpage.write(".B ")
            manpage.write(", ".join(help_opt.opts))
            manpage.write("\nShow command help and exit.\n")

        manpage.write(
            ".SH SEE ALSO\n"
            "mpv(1), yt-dlp(1), youtube-dl(1)\n"
            ".SS Project homepage\n"
            "https://github.com/woefe/ytcc\n"
            ".SS Bug Tracker\n"
            "https://github.com/woefe/ytcc/issues\n"
        )


if __name__ == "__main__":
    main()
