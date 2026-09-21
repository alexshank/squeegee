"""The ``@stage`` decorator and the registry it appends to.

Registration captures what the UI later needs to show: the stage's name, its
description, the exact source that ran, and its annotations where the user
wrote any. Annotations are never required and are never checked.
"""

from __future__ import annotations

import inspect
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, TypeVar, overload

from squeegee.errors import StageDefinitionError

StageFunc = TypeVar("StageFunc", bound=Callable[..., Any])


@dataclass(frozen=True)
class Stage:
    """One transformation, as registered from a user's script."""

    name: str
    description: str | None
    func: Callable[[Any], Any]
    source_text: str
    source_sha256: str
    input_type: str | None
    output_type: str | None


_registry: list[Stage] = []


def registered_stages() -> list[Stage]:
    """Return the registered stages in declaration order."""
    return list(_registry)


def clear_registry() -> None:
    """Forget every registered stage.

    Running two scripts in one process, which the tests do constantly, would
    otherwise accumulate stages across runs.
    """
    _registry.clear()


@overload
def stage(func: StageFunc) -> StageFunc: ...


@overload
def stage(
    *, name: str | None = None, description: str | None = None
) -> Callable[[StageFunc], StageFunc]: ...


def stage(
    func: StageFunc | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> StageFunc | Callable[[StageFunc], StageFunc]:
    """Register a function as the next stage of the pipeline.

    Works bare or called with keyword arguments. The function is returned
    unchanged, so a script's stages stay directly callable and testable.

    Args:
        func: The stage function, when used as a bare decorator.
        name: Overrides the name shown in the UI. Defaults to the function name.
        description: Overrides the description. Defaults to the first docstring line.

    Returns:
        The original function, or the decorator that will return it.
    """

    def register(target: StageFunc) -> StageFunc:
        _reject_unusable(target)
        source = _source_of(target)
        _registry.append(
            Stage(
                name=name or target.__name__,
                description=description or _first_docstring_line(target),
                func=target,
                source_text=source,
                source_sha256=sha256(source.encode()).hexdigest(),
                input_type=_parameter_annotation(target),
                output_type=(
                    _annotation_text(target.__annotations__["return"])
                    if "return" in target.__annotations__
                    else None
                ),
            )
        )
        return target

    return register if func is None else register(func)


def _reject_unusable(func: Callable[..., Any]) -> None:
    if inspect.isasyncgenfunction(func) or inspect.iscoroutinefunction(func):
        raise StageDefinitionError(
            f"stage {func.__name__!r} is async; stages must be ordinary functions"
        )
    if inspect.isgeneratorfunction(func):
        raise StageDefinitionError(
            f"stage {func.__name__!r} is a generator; a stage returns one record, "
            "or None to drop it"
        )
    positional = [
        parameter
        for parameter in inspect.signature(func).parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if len(positional) != 1:
        raise StageDefinitionError(
            f"stage {func.__name__!r} takes {len(positional)} positional parameters; "
            "a stage takes exactly one, the record"
        )


def _source_of(func: Callable[..., Any]) -> str:
    # a stage defined in a REPL or an exec'd string has no retrievable source, which
    # is worth recording honestly rather than failing the run over
    try:
        return textwrap.dedent(inspect.getsource(func))
    except (OSError, TypeError):
        return f"# source unavailable for {func.__name__}\n"


def _first_docstring_line(func: Callable[..., Any]) -> str | None:
    docstring = inspect.getdoc(func)
    return docstring.splitlines()[0] if docstring else None


def _parameter_annotation(func: Callable[..., Any]) -> str | None:
    for key, annotation in func.__annotations__.items():
        if key != "return":
            return _annotation_text(annotation)
    return None


def _annotation_text(annotation: object) -> str:
    # presence is decided by the caller, so an explicit "-> None" is recorded as an
    # annotation rather than mistaken for an absent one
    if annotation is None:
        return "None"
    if isinstance(annotation, str):
        return annotation
    # objects render as "dict[str, typing.Any]"; the typing prefix is noise in a UI
    return str(annotation).replace("typing.", "")
