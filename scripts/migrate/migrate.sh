#!/bin/sh

set -e

ytcc1_major="$(ytcc --version | head -n1 | sed -r -e 's/.+version //' -e 's/^([^.]+).*/\1/')"
if [ -z "${ytcc1_major}" -o "${ytcc1_major}" -ne "1" ]; then
	echo ytcc major version should be 1. Is actually ${ytcc1_major}. >&2
	echo You shouldn\'t have installed version 2 prior to running this script. >&2
	exit 1
fi

if [ $# -ne 1 ]; then
	echo This script takes a single argument: the directory of the ytcc v2 source code. >&2
	echo Please git clone it somewhere. >&2
	exit 1
fi

if ! python -c 'import click' >/dev/null; then
	echo You need to install the python package \'click\' prior to running this script. >&2
	echo It is a new dependancy of ytcc v2 >&2
	exit 1
fi

if ! [ -d "$1" -a -d "$1/ytcc" -a -f "$1/ytcc.py" ]; then
	echo The source code directory specified by the argument doesn\'t look right. >&2
	echo Please make sure you specify the root of the git repository, not the \'ytcc\' directory inside it. >&2
	exit 1
fi

ytcc2_major="$(PYTHONPATH="$1:${PYTHONPATH}" python3.8 -c 'import ytcc; print(ytcc.__version__)' | sed -re 's/^([^.]+).*/\1/')"
if [ -z "${ytcc2_major}" -o "${ytcc2_major}" -ne "2" ]; then
	echo ytcc major version for the source directory should be 2. Is actually ${ytcc2_major}. >&2
	exit 1
fi

if [ -f './ytcc2.db' ]; then
	echo ./ytcc2.db already exists, things might get weird. Delete it for a consistent clean slate >&2
fi

if ! [ -f 'videos.pickle' -o -f 'channels.pickle' ]; then
	echo Exporting database to videos.pickle and channels.pickle
	python3.8 ./export_db.py
	echo Export complete
elif [ -f 'videos.pickle' -a -f 'channels.pickle' ]; then
	echo Skipping export because both pickle files are exported
else
	echo One of the pickle files is present, please delete it and re-run this script.
	exit 1
fi

echo Importing database to ./ytcc2.db
PYTHONPATH="$1:${PYTHONPATH}" python3.8 ./import_db.py
echo Finished
