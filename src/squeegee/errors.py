"""Errors raised at the developer who is using Squeegee.

Every message names the stage, file, or record at fault, so a traceback is
never the only thing a developer has to work from.
"""


class SqueegeeError(Exception):
    """Base class for every error Squeegee raises on purpose."""


class StageDefinitionError(SqueegeeError):
    """A stage function cannot be used as a stage."""


class FormatError(SqueegeeError):
    """A file's format is unsupported, or its contents do not match it."""
