#!/usr/bin/env python3

from glob import glob
from pathlib import Path
from subprocess import run
from setuptools import setup
import ytcc


def compile_translations():
    po_files = glob("po/*.po")
    package_data = []
    for file in po_files:
        lang = file[3:][:-3]
        package_data_file = "resources/locale/" + lang + "/LC_MESSAGES/ytcc.mo"
        out_file = Path("ytcc").joinpath(package_data_file)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        if run(["msgfmt", "-o", str(out_file), file]).returncode == 0:
            package_data.append(package_data_file)

    return package_data


setup(
    name='ytcc',
    description='A YouTube subscription tool',
    long_description=ytcc.__doc__,
    version=ytcc.__version__,
    url='https://github.com/popeye123/ytcc',
    author=ytcc.__author__,
    author_email=ytcc.__email__,
    license=ytcc.__license__,
    scripts=['scripts/ytcc'],
    packages=['ytcc'],
    install_requires=['lxml', 'feedparser>=5.2.0', 'python-dateutil', 'youtube_dl'],
    package_data={
        'ytcc': compile_translations()
    },
)
