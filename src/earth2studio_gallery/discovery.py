from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from .config import GalleryConfig
from .parser import example_metadata


@dataclass(frozen=True, slots=True)
class Example:
    """A discovered example and its presentation metadata."""

    source: Path
    relative: Path
    slug: str
    title: str
    summary: str
    section: str


def discover(config: GalleryConfig, selectors: list[str] | None = None) -> list[Example]:
    """Discover examples and optionally filter them with CLI-style selectors."""
    examples: list[Example] = []
    for source in sorted(config.examples_dir.rglob(config.pattern)):
        if source.name.startswith("_") or source.name.endswith(".gallery.py"):
            continue
        relative = source.relative_to(config.examples_dir)
        title, summary = example_metadata(source)
        section = relative.parent.as_posix() if relative.parent != Path(".") else "Examples"
        slug = "-".join(relative.with_suffix("").parts)
        examples.append(Example(source, relative, slug, title, summary, section))
    return select_examples(examples, selectors)


def select_examples(examples: list[Example], selectors: list[str] | None) -> list[Example]:
    """Filter an existing discovery result without reparsing source files."""
    if not selectors:
        return examples
    return [
        example
        for example in examples
        if any(
            _matches(example.relative.as_posix(), example.source.stem, selector)
            for selector in selectors
        )
    ]


def _matches(path: str, stem: str, selector: str) -> bool:
    selector = selector.replace("\\", "/").strip("/")
    return (
        path == selector
        or path.removesuffix(".py") == selector.removesuffix(".py")
        or path.startswith(f"{selector}/")
        or stem == selector
        or fnmatch.fnmatch(path, selector)
        or fnmatch.fnmatch(path.removesuffix(".py"), selector)
    )
