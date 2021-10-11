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

tagname=$1

if ! echo "$tagname" | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+'; then
    echo "Usage: $0 major.minor.patch"
    exit 1
fi

sed -i -e "s/^__version__ = .*$/__version__ = \"$tagname\"/" ytcc/__init__.py
python3 scripts/make_doc.py doc/ytcc.1

_YTCC_COMPLETE=zsh_source ytcc > scripts/completions/zsh/_ytcc
_YTCC_COMPLETE=bash_source ytcc > scripts/completions/bash/ytcc.completion.sh
_YTCC_COMPLETE=fish_source ytcc > scripts/completions/fish/ytcc.fish

git commit ytcc/__init__.py doc/ytcc.1 scripts/completions -m "Release version $tagname"
git tag -a "v$tagname" -m "Version $tagname"

git show HEAD
read -rp "Push changes? Ctrl+c to cancel, Enter to push"
git push origin master
git push origin "v$tagname"
