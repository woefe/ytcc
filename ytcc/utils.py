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

import importlib
from typing import TypeVar, Optional, Iterable, Any

# pylint: disable=invalid-name
T = TypeVar("T")


def take(amount: int, iterable: Iterable[T]) -> Iterable[T]:
    """Take the first elements of an iterable.

    If the given iterable has less elements than the given amount, the returned iterable has the
    same amount of elements as the given iterable. Otherwise the returned iterable has `amount`
    elements.

    :param amount: The number of elements to take
    :param iterable: The iterable to take elements from
    :return: The first elements of the given iterable
    """
    for _, elem in zip(range(amount), iterable):
        yield elem


def lazy_import(fullname: str, fallback: Optional[str] = None) -> Any:
    """Import a module lazily.

    This is useful for large modules or modules that run slow code on import.

    :param fullname: The module to import
    :param fallback: The module if `fullname` module cannot be found
    :return: A proxy object that lazily loads the module as soon as attributes are accessed.
    """
    class _LazyLoader:
        def __init__(self):
            self._mod = None

        def __getattr__(self, item):
            if self._mod is None:
                try:
                    self._mod = importlib.import_module(fullname)
                except ImportError:
                    self._mod = importlib.import_module(fallback)
            return getattr(self._mod, item)

    return _LazyLoader()
