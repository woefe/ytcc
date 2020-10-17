#!/usr/bin/env bash

tagname=$1

if ! echo "$tagname" | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+'; then
    echo "Usage: $0 major.minor.patch"
    exit 1
fi

sed -i -e "s/^__version__ = .*$/__version__ = \"$tagname\"/" ytcc/__init__.py
python3 scripts/make_doc.py doc/ytcc.1

git commit ytcc/__init__.py -m "Release version $tagname"
git tag -a "v$tagname" -m "Version $tagname"

git show HEAD
read -rp "Push changes? Ctrl+c to cancel, Enter to push"
git push origin master
git push origin "v$tagname"
