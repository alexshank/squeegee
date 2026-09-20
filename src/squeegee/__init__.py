"""Observable cleaning and transforming of small data.

The public API is deliberately small: a ``stage`` decorator, and a ``run``
entry point. Neither exists yet; see ``docs/technical-specification.md``.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("squeegee")
except PackageNotFoundError:  # pragma: no cover - only hit when running from a source tree
    __version__ = "0.0.0"

__all__ = ["__version__"]
