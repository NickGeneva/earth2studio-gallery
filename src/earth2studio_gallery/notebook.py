from __future__ import annotations

import base64
import json
import tomllib
from pathlib import Path

from .config import GalleryConfig
from .discovery import Example
from .parser import cells, markdown
from .runner import RunResult


def build_notebook(
    example: Example,
    result: RunResult | None,
    config: GalleryConfig,
    destination: Path,
) -> None:
    events: dict[int, dict[str, object]] = {}
    for event in result.events if result else []:
        index = event.get("cell")
        if isinstance(index, (int, str)):
            events[int(index)] = event
    images: dict[int, list[Path]] = {}
    if result:
        artifact_dir = config.cache_dir / "runs" / example.slug / "artifacts"
        for artifact in result.artifacts:
            try:
                index = int(artifact.split("-cell-", 1)[1].split(".", 1)[0])
            except (IndexError, ValueError):
                index = -1
            images.setdefault(index, []).append(artifact_dir / artifact)

    notebook_cells: list[dict[str, object]] = []
    execution_count = 0
    for cell in cells(example.source):
        if cell.kind == "markdown":
            notebook_cells.append(
                {
                    "cell_type": "markdown",
                    "id": f"markdown-{cell.index}",
                    "metadata": {},
                    "source": markdown(cell.source, example.source),
                }
            )
            continue
        execution_count += 1
        event = events.get(cell.index, {})
        outputs = _outputs(event, images.get(cell.index, []))
        notebook_cells.append(
            {
                "cell_type": "code",
                "execution_count": execution_count if result and result.returncode == 0 else None,
                "id": f"code-{cell.index}",
                "metadata": {},
                "outputs": outputs,
                "source": cell.source.rstrip() + "\n",
            }
        )

    notebook = {
        "cells": notebook_cells,
        "metadata": {
            "earth2studio_gallery": {
                "source": example.relative.as_posix(),
                "script": _inline_script_metadata(example.source),
            },
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    content = json.dumps(notebook, indent=2, ensure_ascii=False) + "\n"
    if not destination.exists() or destination.read_text(encoding="utf-8") != content:
        destination.write_text(content, encoding="utf-8")


def _outputs(event: dict[str, object], images: list[Path]) -> list[dict[str, object]]:
    outputs: list[dict[str, object]] = []
    for name in ("stdout", "stderr"):
        value = event.get(name)
        if isinstance(value, str) and value:
            outputs.append({"name": name, "output_type": "stream", "text": value})
    for image in images:
        if not image.exists():
            continue
        data = _image_data(image)
        if data:
            outputs.append({"data": data, "metadata": {}, "output_type": "display_data"})
    return outputs


def _image_data(path: Path) -> dict[str, str]:
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    if path.suffix.lower() == ".svg":
        return {"image/svg+xml": path.read_text(encoding="utf-8")}
    mime = mime_types.get(path.suffix.lower())
    if mime is None:
        return {}
    return {mime: base64.b64encode(path.read_bytes()).decode("ascii")}


def _inline_script_metadata(source: Path) -> dict[str, object]:
    lines = source.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "# /// script"), None)
    if start is None:
        return {}
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == "# ///"), None)
    if end is None:
        return {}
    content = "\n".join(
        line.removeprefix("# ").removeprefix("#") for line in lines[start + 1 : end]
    )
    return tomllib.loads(content)
