#!/usr/bin/env bash

#
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
#

set -o pipefail
set -o errexit
set -o nounset

make_table="echo; ytcc --output table list --attributes id,title,publish_date,duration,playlists"

ytcc update

eval "$make_table" |
    fzf --preview "ytcc --output xsv --separator ';' list -a description -i \$(echo {} | cut -d ' ' -f 2)" \
        --layout reverse \
        --preview-window down:55%:wrap \
        --bind "alt-r:reload%ytcc update; $make_table%" \
        --bind "alt-m:reload%echo {} | cut -d ' ' -f 2 | ytcc mark > /dev/null; $make_table%" \
        --bind "enter:execute%echo {} | cut -d ' ' -f 2 | ytcc play%+reload%$make_table%" \
        --header "(enter: watch, alt-r: update, alt-m: mark watched)" \
        --header-lines 3
