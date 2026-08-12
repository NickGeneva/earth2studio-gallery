from __future__ import annotations

import html
import json
import re
from collections.abc import Callable
from pathlib import Path

from .config import GalleryConfig
from .discovery import Example
from .parser import explicit_references
from .progress import ProgressCallback, report

_TARGET = r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+"
_MARKER = re.compile(
    rf"^(?P<indent>[ \t]*)<!--\s*e2sg-backreferences:\s*(?P<target>{_TARGET})\s*-->[ \t]*$",
    re.MULTILINE,
)
_GENERATED = re.compile(
    r"\n?^[ \t]*<!-- e2sg-backreferences-generated:start -->\n.*?"
    r"^[ \t]*<!-- e2sg-backreferences-generated:end -->[ \t]*(?:\n|$)",
    re.MULTILINE | re.DOTALL,
)
_FENCE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})")


def api_reference_pages(config: GalleryConfig) -> dict[str, Path]:
    """Map explicit API markers outside code fences to their Markdown pages."""
    pages: dict[str, Path] = {}
    for page in sorted(config.docs_dir.rglob("*.md")):
        if _is_inside(page, config.output_dir):
            continue
        for target in _marker_targets(page.read_text(encoding="utf-8")):
            pages.setdefault(target, page)
    return pages


def render_backreferences(
    examples: list[Example],
    config: GalleryConfig,
    progress: ProgressCallback | None = None,
) -> None:
    """Write the explicit-reference registry and expand API-page markers."""
    registry = _registry(examples) if config.backreferences else {}
    payload = {
        "version": 1,
        "objects": {
            target: [_registry_entry(example, config) for example in referenced]
            for target, referenced in sorted(registry.items())
        },
    }
    config.cache_dir.mkdir(parents=True, exist_ok=True)
    _write_text_if_changed(
        config.cache_dir / "backreferences.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )

    updated = 0
    markers = 0
    for page in sorted(config.docs_dir.rglob("*.md")):
        if _is_inside(page, config.output_dir):
            continue
        original = page.read_text(encoding="utf-8")
        cleaned = _GENERATED.sub("\n", original)

        rendered, page_markers = _expand_markers(cleaned, page, registry, config)
        markers += page_markers
        if rendered != original:
            _write_text_if_changed(page, rendered)
            updated += 1
    report(
        progress,
        "backrefs",
        (
            f"indexed {len(registry)} API object(s) across {len(examples)} example(s); "
            f"processed {markers} marker(s) on {updated} changed page(s)"
            if config.backreferences
            else f"disabled; removed generated content from {updated} page(s)"
        ),
    )


def _marker_targets(text: str) -> list[str]:
    targets: list[str] = []

    def record(match: re.Match[str]) -> str:
        targets.append(match.group("target"))
        return match.group(0)

    _rewrite_marker_lines(text, record)
    return targets


def _expand_markers(
    text: str,
    page: Path,
    registry: dict[str, list[Example]],
    config: GalleryConfig,
) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        target = match.group("target")
        referenced = registry.get(target, [])
        if not referenced:
            return match.group(0)
        return match.group(0) + "\n" + _cards(page, target, referenced, config)

    return _rewrite_marker_lines(text, replace), count


def _rewrite_marker_lines(text: str, replace: Callable[[re.Match[str]], str]) -> str:
    output: list[str] = []
    fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        match = _FENCE.match(content)
        if fence:
            if (
                match
                and match.group("fence")[0] == fence[0]
                and len(match.group("fence")) >= fence[1]
            ):
                fence = None
            output.append(line)
            continue
        if match:
            token = match.group("fence")
            fence = (token[0], len(token))
            output.append(line)
            continue
        marker = _MARKER.fullmatch(content)
        if marker:
            ending = line[len(content) :]
            output.append(replace(marker) + ending)
        else:
            output.append(line)
    return "".join(output)


def _registry(examples: list[Example]) -> dict[str, list[Example]]:
    registry: dict[str, list[Example]] = {}
    for example in examples:
        for target in sorted(explicit_references(example.source)):
            registry.setdefault(target, []).append(example)
    return registry


def _registry_entry(example: Example, config: GalleryConfig) -> dict[str, str | None]:
    output = config.output_dir.relative_to(config.docs_dir).as_posix()
    page = f"{output}/{example.relative.with_suffix('').as_posix()}/"
    thumbnail_path = config.output_dir / "_assets" / example.slug / "thumbnail.webp"
    thumbnail = (
        f"{output}/_assets/{example.slug}/thumbnail.webp" if thumbnail_path.exists() else None
    )
    return {
        "source": example.relative.as_posix(),
        "title": example.title,
        "summary": example.summary,
        "page": page,
        "thumbnail": thumbnail,
    }


def _cards(page: Path, target: str, examples: list[Example], config: GalleryConfig) -> str:
    output = config.output_dir.relative_to(config.docs_dir)
    page_relative = page.relative_to(config.docs_dir).with_suffix("")
    prefix = "../" * len(page_relative.parts)
    cards: list[str] = []
    for example in examples:
        title = html.escape(example.title)
        summary = html.escape(example.summary)
        link = prefix + (output / example.relative.with_suffix("")).as_posix() + "/"
        thumbnail = config.output_dir / "_assets" / example.slug / "thumbnail.webp"
        if thumbnail.exists():
            source = prefix + (output / "_assets" / example.slug / "thumbnail.webp").as_posix()
            media = (
                f'<img class="e2sg-card-image" src="{source}" alt="Preview of {title}" '
                'loading="lazy">'
            )
        else:
            media = (
                '<div class="e2sg-card-placeholder" aria-hidden="true">'
                '<span class="e2sg-card-placeholder-icon">'
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
                '<path d="M14 2v6h6M10 13l-2 2 2 2M14 13l2 2-2 2"/>'
                "</svg></span></div>"
            )
        cards.append(
            f'<a class="e2sg-gallery-card" href="{link}">{media}'
            f'<span class="e2sg-card-body"><strong>{title}</strong>'
            f'<span class="e2sg-card-summary">{summary}</span></span></a>'
        )
    escaped_target = html.escape(target)
    return "\n".join(
        (
            "<!-- e2sg-backreferences-generated:start -->",
            f'<section class="e2sg-backreferences" data-e2sg-object="{escaped_target}">',
            f"<h2>Examples using <code>{escaped_target}</code></h2>",
            '<div class="e2sg-gallery-grid">',
            *cards,
            "</div>",
            "</section>",
            "<!-- e2sg-backreferences-generated:end -->",
        )
    )


def _is_inside(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def _write_text_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")
