"""Observable cleaning and transforming of small data.

The public API is deliberately small: the ``stage`` decorator, and a ``run``
entry point that does not exist yet. See ``docs/technical-specification.md``.
"""

from importlib.metadata import PackageNotFoundError, version

from squeegee.stages import Stage, stage

try:
    __version__ = version("squeegee")
except PackageNotFoundError:  # pragma: no cover - only hit when running from a source tree
    __version__ = "0.0.0"

__all__ = ["Stage", "__version__", "stage"]
