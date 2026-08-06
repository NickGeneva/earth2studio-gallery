from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    stage: str
    message: str
    example: str | None = None


ProgressCallback = Callable[[ProgressEvent], None]


def report(
    callback: ProgressCallback | None,
    stage: str,
    message: str,
    example: str | None = None,
) -> None:
    if callback is not None:
        callback(ProgressEvent(stage, message, example))
