#!/usr/bin/env python3
from setuptools import setup, find_packages

import ytcc

with open("README.md", "r", encoding="utf-8") as readme:
    long_description = readme.read()

setup(
    name="ytcc",
    description="Command line tool to keep track of your favorite playlists",
    long_description=long_description,
    long_description_content_type="text/markdown",
    version=ytcc.__version__,
    url="https://github.com/woefe/ytcc",
    author=ytcc.__author__,
    author_email=ytcc.__email__,
    license=ytcc.__license__,
    packages=find_packages(exclude=["test"]),
    install_requires=["yt_dlp", "click>=8.0", "wcwidth"],
    extras_require={
      "youtube_dl": ["youtube_dl"]
    },
    python_requires=">=3.7, <4",
    scripts=["scripts/ytccf.sh"],
    entry_points={
        "console_scripts": ["ytcc=ytcc.cli:main"]
    },
    project_urls={
        "Bug Reports": 'https://github.com/woefe/ytcc/issues',
        "Source": 'https://github.com/woefe/ytcc/',
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Video"
    ]
)
