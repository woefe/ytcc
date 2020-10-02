#!/usr/bin/env python3
import logging
from glob import glob
from pathlib import Path
from subprocess import run
from setuptools import setup, find_packages
import ytcc


def compile_translations():
    po_files = glob("po/*.po")
    package_data = []
    for file in po_files:
        lang = file[3:][:-3]
        package_data_file = "resources/locale/" + lang + "/LC_MESSAGES/ytcc.mo"
        out_file = Path("ytcc").joinpath(package_data_file)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            res = run(["msgfmt", "-o", str(out_file), file])
        except FileNotFoundError:
            logging.warning("msgfmt command not found. Ignoring translations")
        else:
            if res.returncode == 0:
                package_data.append(package_data_file)

    return package_data


with open("README.md", "r") as readme:
    long_description = readme.read()

setup(
    name="ytcc",
    description="A subscription wrapper for youtube-dl playlists",
    long_description=long_description,
    long_description_content_type="text/markdown",
    version=ytcc.__version__,
    url="https://github.com/woefe/ytcc",
    author=ytcc.__author__,
    author_email=ytcc.__email__,
    license=ytcc.__license__,
    packages=find_packages(exclude=["test"]),
    install_requires=["youtube_dl", "click"],
    python_requires=">=3.7, <4",
    entry_points={
        "console_scripts": ["ytcc=ytcc.cli:main"]
    },
    package_data={
        "ytcc": compile_translations()
    },
    project_urls={
        "Bug Reports": 'https://github.com/woefe/ytcc/issues',
        "Source": 'https://github.com/woefe/ytcc/',
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Video"
    ]
)
