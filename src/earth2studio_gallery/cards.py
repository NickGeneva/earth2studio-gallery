"""Shared HTML rendering for gallery cards."""

from __future__ import annotations

import html

from .discovery import Example


def render_gallery_card(
    example: Example,
    *,
    href: str,
    thumbnail_url: str | None = None,
    status: tuple[str, str] | None = None,
) -> str:
    """Return one Material-compatible example card."""
    title = html.escape(example.title)
    summary = html.escape(example.summary)
    if thumbnail_url:
        media = (
            f'<img class="e2sg-card-image" src="{html.escape(thumbnail_url, quote=True)}" '
            f'alt="Preview of {title}" loading="lazy">'
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
    meta = ""
    if status:
        name, label = status
        meta = (
            f'<span class="e2sg-card-meta e2sg-card-meta--{html.escape(name)}">'
            f"{html.escape(label)}</span>"
        )
    return (
        f'<a class="e2sg-gallery-card" href="{html.escape(href, quote=True)}">{media}'
        f'<span class="e2sg-card-body"><strong>{title}</strong>'
        f'<span class="e2sg-card-summary">{summary}</span>{meta}</span></a>'
    )
