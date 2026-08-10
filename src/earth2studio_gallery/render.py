from __future__ import annotations

import html
import io
import re
import shutil
from pathlib import Path

from PIL import Image, ImageOps

from .config import GalleryConfig
from .discovery import Example
from .notebook import build_notebook
from .parser import cells, markdown
from .progress import ProgressCallback, report
from .runner import RunResult
from .telemetry_render import telemetry_panel


def render_example(
    example: Example,
    result: RunResult | None,
    config: GalleryConfig,
    progress: ProgressCallback | None = None,
) -> Path:
    name = example.relative.as_posix()
    report(progress, "render", "converting cells to Markdown", name)
    relative = example.relative.with_suffix(".md")
    target = config.output_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    asset_dir = config.output_dir / "_assets" / example.slug
    asset_dir.mkdir(parents=True, exist_ok=True)
    events: dict[int, dict[str, object]] = {}
    for item in result.events if result else []:
        cell = item.get("cell")
        if isinstance(cell, (int, str)):
            events[int(cell)] = item
    artifact_map: dict[int, list[str]] = {}
    if result:
        run_artifacts = config.cache_dir / "runs" / example.slug / "artifacts"
        for artifact in result.artifacts:
            source = run_artifacts / artifact
            if source.exists():
                web_artifact = _prepare_web_image(
                    source,
                    asset_dir / artifact,
                    config,
                    progress=progress,
                    example=name,
                )
                try:
                    cell_number = int(artifact.split("-cell-", 1)[1].split(".", 1)[0])
                except (IndexError, ValueError):
                    cell_number = -1
                artifact_map.setdefault(cell_number, []).append(web_artifact)
        thumbnail = run_artifacts / "thumbnail.webp"
        if thumbnail.exists():
            _copy_if_changed(thumbnail, asset_dir / "thumbnail.webp")

    output: list[str] = []
    for cell in cells(example.source):
        if cell.kind == "markdown":
            output.append(markdown(cell.source, example.source))
        else:
            output.append(f"```python\n{cell.source.rstrip()}\n```")
            event = events.get(cell.index, {})
            stdout = str(event.get("stdout", "")).strip()
            stderr = str(event.get("stderr", "")).strip()
            if stdout:
                output.append(f'```text title="Output"\n{stdout}\n```')
            if stderr:
                indented_stderr = stderr.replace("\n", "\n    ")
                output.append(
                    f'??? warning "Standard error"\n\n    ```text\n    {indented_stderr}\n    ```'
                )
            for artifact in artifact_map.get(cell.index, []):
                path = (
                    Path("../" * len(relative.parent.parts)) / "_assets" / example.slug / artifact
                )
                output.append(_output_image(example, path))
    for artifact in artifact_map.get(-1, []):
        path = Path("../" * len(relative.parent.parts)) / "_assets" / example.slug / artifact
        output.append(_output_image(example, path))
    source_asset = asset_dir / example.source.name
    _copy_if_changed(example.source, source_asset)
    # Raw HTML links are not rewritten by MkDocs from the Markdown source path
    # to its directory-style page URL, which adds one more path component.
    asset_prefix = Path("../" * (len(relative.parent.parts) + 1)) / "_assets" / example.slug
    source_link = (asset_prefix / source_asset.name).as_posix()
    downloads = [
        f'<a class="e2sg-download" href="{source_link}" download>Download Python source</a>'
    ]
    if config.generate_notebooks:
        notebook_asset = asset_dir / example.source.with_suffix(".ipynb").name
        build_notebook(example, result, config, notebook_asset)
        notebook_link = (asset_prefix / notebook_asset.name).as_posix()
        downloads.append(
            f'<a class="e2sg-download" href="{notebook_link}" download>'
            "Download Jupyter notebook</a>"
        )
        report(progress, "notebook", f"generated {notebook_asset.name}", name)
    timing = f" · executed in {result.duration:.1f}s" if result else ""
    output.append(
        '---\n\n<div class="e2sg-downloads">'
        + "".join(downloads)
        + f'<span class="e2sg-download-meta">{timing.removeprefix(" · ")}</span></div>'
    )
    if result and result.telemetry:
        output.append(telemetry_panel(result, example.source))
        report(progress, "telemetry", "rendered runtime telemetry panel", name)
    _write_text_if_changed(target, "\n\n".join(item for item in output if item).rstrip() + "\n")
    report(progress, "render", f"wrote {target.relative_to(config.docs_dir).as_posix()}", name)
    return target


def _output_image(example: Example, path: Path) -> str:
    return (
        f"![Output from {html.escape(example.title)}]({path.as_posix()})"
        "{ .e2sg-output-image loading=lazy }"
    )


def render_indexes(
    examples: list[Example], results: dict[str, RunResult | None], config: GalleryConfig
) -> None:
    by_section: dict[str, list[Example]] = {}
    for example in examples:
        by_section.setdefault(example.section, []).append(example)
    main: list[str] = [
        "# Example gallery",
        "",
        "Runnable examples, grouped by topic. Each card opens the complete source, output, "
        "and captured figures.",
    ]
    for section, items in by_section.items():
        section_dir = config.output_dir / section
        section_dir.mkdir(parents=True, exist_ok=True)
        stale_index = section_dir / "index.md"
        if stale_index.exists():
            stale_index.unlink()
        section_name = re.sub(r"^\d+[_-]*", "", Path(section).name).replace("_", " ").title()
        main.extend(["", f"## {section_name}", "", '<div class="e2sg-gallery-grid">'])
        for example in items:
            result = results.get(example.slug)
            thumb = config.output_dir / "_assets" / example.slug / "thumbnail.webp"
            title = html.escape(example.title)
            summary = html.escape(example.summary)
            if thumb.exists():
                media = (
                    f'<img class="e2sg-card-image" src="_assets/{example.slug}/thumbnail.webp" '
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
            link = example.relative.with_suffix("").as_posix() + "/"
            meta = ""
            if result:
                if result.stale:
                    label = "Stale"
                    status = "stale"
                elif result.cached:
                    label = "Cached"
                    status = "cached"
                else:
                    label = f"Ran in {result.duration:.1f}s"
                    status = "ran"
            else:
                label = "Missing"
                status = "missing"
            meta = f'<span class="e2sg-card-meta e2sg-card-meta--{status}">{label}</span>'
            main.append(
                f'<a class="e2sg-gallery-card" href="{link}">'
                f'{media}<span class="e2sg-card-body"><strong>{title}</strong>'
                f'<span class="e2sg-card-summary">{summary}</span>{meta}</span></a>'
            )
        main.append("</div>")
    config.output_dir.mkdir(parents=True, exist_ok=True)
    _write_text_if_changed(config.output_dir / "index.md", "\n".join(main) + "\n")


def write_css(config: GalleryConfig) -> Path:
    target = config.docs_dir / "assets" / "stylesheets" / "earth2studio-gallery.css"
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_text_if_changed(target, _CSS)
    return target


def _write_text_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def _copy_if_changed(source: Path, destination: Path) -> None:
    if (
        destination.exists()
        and source.stat().st_size == destination.stat().st_size
        and source.read_bytes() == destination.read_bytes()
    ):
        return
    shutil.copy2(source, destination)


def _prepare_web_image(
    source: Path,
    destination: Path,
    config: GalleryConfig,
    *,
    progress: ProgressCallback | None = None,
    example: str | None = None,
) -> str:
    raster_suffixes = {".png", ".jpg", ".jpeg", ".webp"}
    if not config.optimize_images or source.suffix.lower() not in raster_suffixes:
        _copy_if_changed(source, destination)
        report(progress, "image", f"preserved {source.name}", example)
        return destination.name
    with Image.open(source) as opened:
        should_optimize = (
            source.stat().st_size >= config.image_min_bytes
            or opened.width > config.image_max_width
            or opened.height > config.image_max_height
        )
        if not should_optimize:
            _copy_if_changed(source, destination)
            report(
                progress,
                "image",
                f"kept {source.name} ({_human_bytes(source.stat().st_size)}; below limits)",
                example,
            )
            return destination.name
        original_size = source.stat().st_size
        original_dimensions = f"{opened.width}×{opened.height}"
        image = ImageOps.exif_transpose(opened)
        mode = "RGBA" if "A" in image.getbands() else "RGB"
        image = image.convert(mode)
        image.thumbnail(
            (config.image_max_width, config.image_max_height),
            Image.Resampling.LANCZOS,
            reducing_gap=3.0,
        )
        buffer = io.BytesIO()
        image.save(buffer, "WEBP", quality=config.image_quality, method=4)
    web_destination = destination.with_suffix(".webp")
    content = buffer.getvalue()
    if not web_destination.exists() or web_destination.read_bytes() != content:
        web_destination.write_bytes(content)
    if destination != web_destination and destination.exists():
        destination.unlink()
    report(
        progress,
        "image",
        f"optimized {source.name}: {original_dimensions} {_human_bytes(original_size)} → "
        f"{image.width}×{image.height} WebP {_human_bytes(len(content))}",
        example,
    )
    return web_destination.name


def _human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


_CSS = """.md-grid { max-width: 88rem; }

.e2sg-gallery-grid {
  display: grid;
  grid-template-columns: repeat(
    auto-fill,
    minmax(
      min(100%, var(--e2sg-gallery-card-width, 12rem)),
      var(--e2sg-gallery-card-width, 12rem)
    )
  );
  gap: 1.1rem;
  justify-content: start;
  margin: 1rem 0 2.5rem;
}

.e2sg-gallery-card {
  display: flex;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  color: var(--md-typeset-color) !important;
  background: var(--md-code-bg-color);
  border: 1px solid var(--md-default-fg-color--lightest);
  border-radius: .65rem;
  box-shadow: 0 .15rem .5rem rgb(0 0 0 / 8%);
  text-decoration: none !important;
  transition: border-color 150ms ease, box-shadow 150ms ease, transform 150ms ease;
}

.md-typeset a.e2sg-gallery-card { text-decoration: none !important; }

.e2sg-gallery-card:hover {
  border-color: var(--md-accent-fg-color);
  box-shadow: 0 .45rem 1.15rem rgb(0 0 0 / 16%);
  transform: translateY(-2px);
}

.e2sg-card-image,
.e2sg-card-placeholder {
  display: block;
  width: 100%;
  aspect-ratio: 3 / 2;
  object-fit: cover;
  background: var(--md-default-bg-color);
  border-bottom: 1px solid var(--md-default-fg-color--lightest);
}

.e2sg-card-placeholder {
  display: grid;
  place-items: center;
  background:
    radial-gradient(
      circle at 1px 1px,
      var(--md-default-fg-color--lightest) 1px,
      transparent 0
    ) 0 0 / 18px 18px,
    linear-gradient(135deg, var(--md-code-bg-color), var(--md-default-bg-color));
}

.e2sg-card-placeholder-icon {
  display: grid;
  width: 3.5rem;
  height: 3.5rem;
  place-items: center;
  color: var(--md-primary-bg-color);
  background: var(--md-accent-fg-color);
  border-radius: .75rem;
}

.e2sg-card-placeholder-icon svg {
  width: 1.65rem;
  height: 1.65rem;
}

.e2sg-card-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: .4rem;
  padding: .9rem 1rem 1rem;
}

.e2sg-card-body strong {
  color: var(--md-accent-fg-color);
  font-size: .9rem;
  line-height: 1.3;
}

.e2sg-card-summary {
  display: -webkit-box;
  overflow: hidden;
  color: var(--md-default-fg-color--light);
  font-size: .72rem;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}

.e2sg-card-meta {
  margin-top: auto;
  padding-top: .35rem;
  color: var(--md-default-fg-color--lighter);
  font-size: .62rem;
  letter-spacing: .02em;
}

.e2sg-card-meta--ran { color: var(--md-typeset-a-color); }
.e2sg-card-meta--stale { color: var(--md-code-hl-string-color); }
.e2sg-card-meta--missing { color: var(--md-code-hl-special-color); }

.md-typeset img.e2sg-output-image {
  display: block;
  width: auto;
  max-width: 100%;
  max-height: 36rem;
  margin: 1.5rem auto;
  border-radius: .4rem;
}

.e2sg-downloads {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: .65rem;
  margin-top: 1rem;
}

.e2sg-download {
  display: inline-flex;
  align-items: center;
  min-height: 2.2rem;
  padding: .45rem .85rem;
  color: var(--md-primary-bg-color) !important;
  background: var(--md-accent-fg-color);
  border-radius: .3rem;
  font-size: .7rem;
  font-weight: 700;
  text-decoration: none !important;
}

.md-typeset a.e2sg-download { text-decoration: none !important; }

.e2sg-download:hover { filter: brightness(1.08); }

.e2sg-download-meta {
  color: var(--md-default-fg-color--lighter);
  font-size: .65rem;
}

.e2sg-telemetry {
  margin: 2rem 0 .5rem;
  padding: 1.15rem;
  color: var(--md-typeset-color);
  background: var(--md-default-bg-color);
  border: .05rem solid var(--md-typeset-table-color);
  border-top: .2rem solid var(--md-typeset-a-color);
  border-radius: .2rem;
  box-shadow: var(--md-shadow-z1);
}

.e2sg-telemetry-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.e2sg-eyebrow {
  color: var(--md-typeset-a-color);
  font-size: .56rem;
  font-weight: 700;
  letter-spacing: .12em;
  text-transform: uppercase;
}

.md-typeset .e2sg-telemetry h2,
.md-typeset .e2sg-telemetry h3 { margin: 0; }

.md-typeset .e2sg-telemetry h2 {
  font-size: 1.15rem;
  line-height: 1.3;
}

.e2sg-sample-count {
  padding: .25rem .5rem;
  color: var(--md-default-fg-color--light);
  background: var(--md-code-bg-color);
  border: .05rem solid var(--md-typeset-table-color);
  border-radius: 999px;
  font-size: .55rem;
  white-space: nowrap;
}

.e2sg-metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
  gap: .65rem;
}

.e2sg-metric {
  display: flex;
  min-width: 0;
  flex-direction: column;
  padding: .7rem;
  overflow: hidden;
  background: var(--md-code-bg-color);
  border: .05rem solid var(--md-typeset-table-color);
  border-radius: .2rem;
}

.e2sg-metric-label,
.e2sg-metric-context {
  color: var(--md-default-fg-color--light);
  font-size: .55rem;
}

.e2sg-metric strong {
  margin-top: .15rem;
  color: var(--md-code-fg-color);
  font-family: var(--md-code-font-family);
  font-size: 1.15rem;
  font-variant-numeric: tabular-nums;
}

.e2sg-sparkline,
.e2sg-spark-empty {
  width: 100%;
  height: 1.65rem;
  margin-top: .5rem;
}

.e2sg-sparkline polyline {
  fill: none;
  stroke: var(--md-typeset-a-color);
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
}

.e2sg-sparkline .e2sg-spark-grid {
  fill: none;
  stroke: var(--md-code-bg-color--lighter);
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
}

.md-typeset .e2sg-telemetry-subtitle {
  margin-top: 1.15rem;
  margin-bottom: .55rem;
  color: var(--md-default-fg-color--light);
  font-size: .63rem;
  font-weight: 700;
  letter-spacing: .05em;
  text-transform: uppercase;
}

.e2sg-timings { padding-top: 1.35rem; }

.e2sg-telemetry > .e2sg-telemetry-subtitle {
  padding-top: 1.35rem;
  padding-bottom: .4rem;
}

.e2sg-timing-row {
  display: grid;
  grid-template-columns: minmax(5.5rem, 1fr) minmax(7rem, 3fr) 3.5rem;
  align-items: center;
  gap: .65rem;
  margin: .4rem 0;
  font-size: .62rem;
}

.e2sg-timing-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.e2sg-timing-track {
  height: .38rem;
  overflow: hidden;
  background: var(--md-code-bg-color--lighter);
  border-radius: 999px;
}

.e2sg-timing-bar {
  display: block;
  height: 100%;
  background: var(--md-typeset-a-color);
  border-radius: inherit;
}

.e2sg-timing-row strong {
  color: var(--md-code-fg-color);
  font-family: var(--md-code-font-family);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.e2sg-hardware-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 1px;
  overflow: hidden;
  background: var(--md-typeset-table-color);
  border: .05rem solid var(--md-typeset-table-color);
  border-radius: .2rem;
}

.e2sg-hardware-item {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: .12rem;
  padding: .55rem .65rem;
  background: var(--md-default-bg-color);
}

.e2sg-hardware-item span {
  color: var(--md-default-fg-color--lighter);
  font-size: .5rem;
  font-weight: 700;
  letter-spacing: .05em;
  text-transform: uppercase;
}

.e2sg-hardware-item strong {
  overflow: hidden;
  font-size: .62rem;
  font-weight: 500;
  text-overflow: ellipsis;
}

@media screen and (max-width: 38rem) {
  .e2sg-gallery-grid {
    grid-template-columns: repeat(
      auto-fill,
      minmax(
        min(100%, var(--e2sg-gallery-card-mobile-width, 10rem)),
        var(--e2sg-gallery-card-mobile-width, 10rem)
      )
    );
    gap: .75rem;
  }

  .e2sg-telemetry { padding: .85rem; }
  .e2sg-timing-row { grid-template-columns: minmax(4rem, 1fr) 2fr 3rem; }
}
"""
