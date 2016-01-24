#!/usr/bin/env bash

if [[ -z $1 || $1 == "-h" ]]; then
    echo "Usage: $0 major.minor.patch"
    exit 1
fi

tagname=$1
sed -i -e "s/^__version__ = .*$/__version__ = \"$tagname\"/" ytcc/__init__.py

git tag -a v$tagname -m "Version $tagname"
git push origin $tagname
