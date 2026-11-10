import pytest

from ytcc.config import Color


def test_color_rejects_out_of_range():
    with pytest.raises(ValueError):
        Color(-1)
    with pytest.raises(ValueError):
        Color(256)


def test_color_accepts_boundaries():
    assert Color(0) == 0
    assert Color(255) == 255
    assert Color(100) == 100
