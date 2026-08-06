from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from earth2studio_gallery.builder import GalleryBuilder
from earth2studio_gallery.config import GalleryConfig
from earth2studio_gallery.progress import ProgressEvent
from earth2studio_gallery.runner import _script_metadata


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is required for execution")
def test_executes_captures_and_caches(tmp_path: Path) -> None:
    (tmp_path / "gallery.toml").write_text(
        """[gallery]
image_max_width = 10
image_max_height = 10
image_min_bytes = 0
collect_telemetry = true
telemetry_interval = 0.25
""",
        encoding="utf-8",
    )
    example = tmp_path / "examples" / "basics" / "plot.py"
    example.parent.mkdir(parents=True)
    example.write_text(
        '''# %%
"""Tiny Plot
=========

An integration test.
"""
# /// script
# dependencies = ["pillow>=11"]
# ///
# %%
print("cell output")
from PIL import Image
Image.new("RGB", (20, 10), "red").save("result.png")
''',
        encoding="utf-8",
    )
    config = GalleryConfig.load(tmp_path)
    progress: list[ProgressEvent] = []
    first = GalleryBuilder(config, progress=progress.append).build()
    result = next(item for item in first.results.values() if item)
    assert result.returncode == 0
    assert result.artifacts
    assert result.telemetry["summary"]
    assert result.telemetry["system"]
    assert any(event.get("duration") is not None for event in result.events)
    page = tmp_path / "docs" / "gallery" / "basics" / "plot.md"
    assert "cell output" in page.read_text(encoding="utf-8")
    assert "Download Jupyter notebook" in page.read_text(encoding="utf-8")
    assert "Runtime telemetry" in page.read_text(encoding="utf-8")
    assert (tmp_path / "docs" / "gallery" / "_assets" / "basics-plot" / "thumbnail.webp").exists()
    second = GalleryBuilder(config).build()
    assert next(item for item in second.results.values() if item).cached
    gallery_path = tmp_path / "docs" / "gallery" / "index.md"
    gallery_modified = gallery_path.stat().st_mtime_ns
    retained = GalleryBuilder(config).build(execute="never")
    retained_result = next(item for item in retained.results.values() if item)
    assert retained_result.cached
    assert not retained_result.stale
    assert gallery_path.stat().st_mtime_ns == gallery_modified
    assert "001-cell-1.webp" in page.read_text(encoding="utf-8")
    web_image = tmp_path / "docs" / "gallery" / "_assets" / "basics-plot" / "001-cell-1.webp"
    with Image.open(web_image) as image:
        assert image.size == (10, 5)
    notebook_path = tmp_path / "docs" / "gallery" / "_assets" / "basics-plot" / "plot.ipynb"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert any(output.get("name") == "stdout" for output in code_cells[-1]["outputs"])
    assert any("image/png" in output.get("data", {}) for output in code_cells[-1]["outputs"])
    stages = {event.stage for event in progress}
    assert {"discover", "prepare", "execute", "capture", "render", "image", "complete"} <= stages
    gallery = gallery_path.read_text(encoding="utf-8")
    assert "## Basics" in gallery
    assert 'class="e2sg-gallery-card"' in gallery
    assert 'href="basics/plot/"' in gallery
    assert 'href="basics/plot.md"' not in gallery
    assert "<small>" not in gallery
    assert not (tmp_path / "docs" / "gallery" / "basics" / "index.md").exists()

    example.write_text(
        example.read_text(encoding="utf-8") + "\n# Source changed\n", encoding="utf-8"
    )
    missing = tmp_path / "examples" / "basics" / "missing.py"
    missing.write_text('# %%\n"""Missing Example\n===============\n"""\n', encoding="utf-8")
    shutil.rmtree(config.output_dir)

    rendered = GalleryBuilder(config).render()
    stale_result = rendered.results["basics-plot"]
    assert stale_result is not None
    assert stale_result.stale
    assert rendered.results["basics-missing"] is None
    assert "cell output" in page.read_text(encoding="utf-8")
    rebuilt_gallery = gallery_path.read_text(encoding="utf-8")
    assert ">Stale</span>" in rebuilt_gallery
    assert ">Missing</span>" in rebuilt_gallery


def test_self_hosted_git_dependency_uses_current_checkout(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo-gallery"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    example = tmp_path / "docs" / "examples" / "example.py"
    example.parent.mkdir(parents=True)
    example.write_text(
        """# /// script
# dependencies = [
#   "demo-gallery @ git+https://github.com/example/demo-gallery.git",
# ]
# ///
""",
        encoding="utf-8",
    )
    metadata = _script_metadata(example, tmp_path)
    assert "git+https" not in metadata
    assert f"demo-gallery @ {tmp_path.as_uri()}" in metadata
