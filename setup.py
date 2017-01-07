#!/usr/bin/env python

from setuptools import setup
import ytcc

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
    install_requires=['lxml', 'feedparser>=5.2.0', 'python-dateutil', 'youtube_dl']
)
