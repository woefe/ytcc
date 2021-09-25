#!/usr/bin/env bash

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

set -o pipefail
set -o errexit
set -o nounset

declare -r -x THUMBNAIL_DIR=$HOME/.cache/ytccf/thumbnails
FILTERS=()
KEY_BINDINGS="
        tab: select/deselect
      enter: play video(s)
  alt-enter: play audio track(s)
      alt-d: download video(s)
      alt-r: update
      alt-m: mark selection as watched
      alt-u: mark last watched video as unwatched
      alt-h: show help"

# shellcheck disable=SC2016
MAKE_TABLE='ytcc --output table --truncate $((2 * $(tput cols) / 3 - 3)) list --attributes id,title,publish_date,duration,playlists'

if command -v ueberzug &> /dev/null || [[ $TERM == "xterm-kitty" ]]; then
    THUMBNAILS=1
else
    THUMBNAILS=0
fi

function draw_preview() { :; }
function clear_preview() { :; }
function init_preview() { :; }
function finalize_preview() { :; }
function fetch_thumbnails() { :; }
function calculate_preview_size() { :; }

function check_cmd() {
    if ! command -v "$1" &> /dev/null; then
        echo "Command '$1' not found. Aborting."
        exit 1
    fi
}

function usage() {
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
      --clear-thumbnails          Empty the thumbnail cache.
      --no-thumbnails             Do not display thumbnails.
  -h, --help                      Show this message and exit.


KEY BINDINGS:$KEY_BINDINGS

For more keybindings see fzf(1).
EOF
}


while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
    -p | --playlists)
        FILTERS+=(-p "$2")
        shift
        shift
        ;;
    -c | --tags)
        FILTERS+=( -c "$2")
        shift
        shift
        ;;
    -s | --since)
        FILTERS+=( -s "$2")
        shift
        shift
        ;;
    -t | --till)
        FILTERS=(-t "$2")
        shift
        shift
        ;;
    -w | --watched)
        FILTERS=(-w)
        shift
        ;;
    -u | --unwatched)
        FILTERS=(-u)
        shift
        ;;
    -h | --help)
        usage
        exit
        ;;
    --no-thumbnails)
        THUMBNAILS=0
        shift
        ;;
    --clear-thumbnails)
        [[ -d "$THUMBNAIL_DIR" ]] && rm -r "$THUMBNAIL_DIR" && echo "Successfully cleared thumbnail cache"
        exit
        ;;
    *)
        echo "Unknown option: $key"
        echo "Try $0 --help for help."
        exit 1
        ;;
    esac
done
MAKE_TABLE="$MAKE_TABLE ${FILTERS[*]}"

check_cmd ytcc
check_cmd fzf

if [[ $THUMBNAILS -eq 1 ]]; then
    check_cmd curl
    check_cmd stty

    function fetch_thumbnails() {
        local -a curl_args=()
        for line in $(ytcc --output xsv list --attributes id,thumbnail_url "${FILTERS[@]}"); do
            read -r -a arr <<< "${line/,/ }"
            if ((${#arr[@]} > 1)) && ! [[ -e $THUMBNAIL_DIR/${arr[0]} ]]; then
                curl_args+=( -o "$THUMBNAIL_DIR/${arr[0]}" "${arr[1]}")
            fi
        done
        mkdir -p "$THUMBNAIL_DIR"
        if (( ${#curl_args[@]} > 0 )); then
            echo INFO: Fetching thumbnails
            curl -L --silent "${curl_args[@]}"
        fi
    }

    function calculate_preview_size() {
        local term_lines term_cols
        read -r term_lines term_cols < <(stty size </dev/tty)
        X=$((2 * term_cols / 3))
        Y=3
        LINES=$((term_lines / 2 - 3))
        COLUMNS=$((term_cols / 3 ))
    }

    if [[ $TERM == "xterm-kitty" ]]; then
        function draw_preview {
            calculate_preview_size
            kitty icat --transfer-mode file -z=-1 --place=${COLUMNS}x${LINES}@${X}x${Y} --scale-up "${@}"
        }
    else
        check_cmd ueberzug
        UEBERZUG_FIFO="$(mktemp --dry-run --suffix "fzf-$$-ueberzug")"
        declare -r -x UEBERZUG_FIFO
        declare -r -x PREVIEW_ID="preview"

        function draw_preview {
            calculate_preview_size
            local -A cmd=( \
                [action]=add
                [identifier]="${PREVIEW_ID}" \
                [x]="${X}" [y]="${Y}" \
                [width]="${COLUMNS}" [height]="${LINES}" \
                [scaler]=fit_contain [scaling_position_x]=0.5 [scaling_position_y]=0.5 \
                [path]="${@}"
            )

            declare -p cmd >"${UEBERZUG_FIFO}"
        }

        function clear_preview {
            local -A cmd=( \
                [action]=remove [identifier]="${PREVIEW_ID}" \
            )
            declare -p cmd >"${UEBERZUG_FIFO}"
        }

        function init_preview {
            mkfifo "${UEBERZUG_FIFO}"
            ueberzug layer --parser bash --silent <"${UEBERZUG_FIFO}" &

            # prevent EOF
            exec 3>"${UEBERZUG_FIFO}"
        }

        function finalize_preview {
            exec 3>&-
            rm "${UEBERZUG_FIFO}" &>/dev/null
            kill "$(jobs -p)" &>/dev/null
        }
    fi
fi

init_preview
trap finalize_preview EXIT
fetch_thumbnails

export -f draw_preview clear_preview fetch_thumbnails calculate_preview_size

eval "$MAKE_TABLE" |
    SHELL=/usr/bin/bash fzf --preview "draw_preview $THUMBNAIL_DIR/{1}; ytcc --output xsv --separator ';' list --watched --unwatched -a description -i {1}" \
        --multi \
        --layout reverse \
        --preview-window down:50%:wrap \
        --bind "enter:execute%clear_preview; ytcc play {+1}%+reload%$MAKE_TABLE%" \
        --bind "alt-enter:execute%clear_preview; ytcc play --audio-only {+1}%+reload%$MAKE_TABLE%" \
        --bind "alt-d:execute%clear_preview; ytcc download {+1}%+reload%$MAKE_TABLE%" \
        --bind "alt-r:execute%clear_preview; ytcc update; fetch_thumbnails%+reload%$MAKE_TABLE%" \
        --bind "alt-h:execute%clear_preview; echo 'Key bindings:$KEY_BINDINGS' | less%+reload%$MAKE_TABLE%" \
        --bind "alt-m:reload%ytcc mark {+1}; $MAKE_TABLE%" \
        --bind "alt-u:reload%ytcc ls --order-by watched desc --watched | head -n1 | ytcc unmark; $MAKE_TABLE%" \
        --header-lines 2
