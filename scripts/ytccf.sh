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

make_table='ytcc --output table --truncate $(($(tput cols) - 3)) list --attributes id,title,publish_date,duration,playlists'
key_bindings="
        tab: select/deselect
      enter: play video(s)
  alt-enter: play audio track(s)
      alt-d: download video(s)
      alt-r: update
      alt-m: mark selection as watched
      alt-u: mark last watched video as unwatched
      alt-h: show help"

check_cmd() {
    if ! command -v "$1" &> /dev/null; then
        echo "Command '$1' not found. Aborting."
        exit 1
    fi
}

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

    An interactive terminal user interface for ytcc based on fzf. The options
    filter which videos are shown. All unwatched videos are shown by default.

OPTIONS:
  -c, --tags COMMA_SEPARATED_VALUES
                                  Listed videos must be tagged with one of the
                                  given tags.

  -s, --since [%Y-%m-%d]          Listed videos must be published after the
                                  given date.

  -t, --till [%Y-%m-%d]           Listed videos must be published before the
                                  given date.

  -p, --playlists COMMA_SEPARATED_VALUES
                                  Listed videos must be in on of the given
                                  playlists.
  -w, --watched                   Only watched videos are listed.
  -u, --unwatched                 Only unwatched videos are listed.
  -h, --help                      Show this message and exit.


KEY BINDINGS:$key_bindings

For more keybindings see fzf(1).
EOF
}


while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
    -p | --playlists)
        make_table="$make_table -p '$2'"
        shift
        shift
        ;;
    -c | --tags)
        make_table="$make_table -c '$2'"
        shift
        shift
        ;;
    -s | --since)
        make_table="$make_table -s '$2'"
        shift
        shift
        ;;
    -t | --till)
        make_table="$make_table -t '$2'"
        shift
        shift
        ;;
    -w | --watched)
        make_table="$make_table -w"
        shift
        ;;
    -u | --unwatched)
        make_table="$make_table -u"
        shift
        ;;
    -h | --help)
        usage
        exit
        ;;
    *)
        echo "Unknown option: $key"
        echo "Try $0 --help for help."
        exit 1
        ;;
    esac
done

check_cmd ytcc
check_cmd fzf

eval "$make_table" |
    fzf --preview "ytcc --output xsv --separator ';' list --watched --unwatched -a description -i {1}" \
        --multi \
        --layout reverse \
        --preview-window down:55%:wrap \
        --bind "enter:execute%ytcc play {+1}%+reload%$make_table%" \
        --bind "alt-enter:execute%ytcc play --audio-only {+1}%+reload%$make_table%" \
        --bind "alt-d:execute%ytcc download {+1}%+reload%$make_table%" \
        --bind "alt-r:execute%ytcc update%+reload%$make_table%" \
        --bind "alt-h:execute%echo 'Key bindings:$key_bindings' | less%+reload%$make_table%" \
        --bind "alt-m:reload%ytcc mark {+1}; $make_table%" \
        --bind "alt-u:reload%ytcc ls --order-by watched desc --watched | head -n1 | ytcc unmark; $make_table%" \
        --header-lines 2
