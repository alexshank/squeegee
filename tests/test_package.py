"""Smoke tests that keep the toolchain honest before any real code exists."""

import squeegee


def test_version_is_exposed() -> None:
    assert isinstance(squeegee.__version__, str)
    assert squeegee.__version__
