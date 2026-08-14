from __future__ import annotations

import json
import tomllib
from pathlib import Path

from .discovery import Example
from .parser import cells, markdown


def build_notebook(example: Example, destination: Path) -> None:
    """Convert an example to a clean, unexecuted Jupyter notebook."""
    notebook_cells: list[dict[str, object]] = []
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
        notebook_cells.append(
            {
                "cell_type": "code",
                "execution_count": None,
                "id": f"code-{cell.index}",
                "metadata": {},
                "outputs": [],
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
