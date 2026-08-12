from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from earth2studio_gallery.builder import GalleryBuilder
from earth2studio_gallery.config import GalleryConfig
from earth2studio_gallery.progress import ProgressEvent
from earth2studio_gallery.render import _console_output, _event_console
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
download_button_color = "#123456"
output_open = true
output_max_height = 321

[gallery.runner.env]
TORCH_ALLOW_TF32_CUBLAS_OVERRIDE = "1"
HF_TOKEN = "not-a-real-secret"
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
# %% tags=["e2sg-profile:inference"]
import sys

print("cell output")
print("progress written to stderr", file=sys.stderr)
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
    assert result.telemetry["summary"]["network_received_bytes"] is not None
    assert result.telemetry["regions"][0]["name"] == "inference"
    assert result.environment["python"]["version"]
    assert result.environment["python"]["uv_environment"].startswith("harness-")
    assert result.environment["uv"]["version"].startswith("uv ")
    assert result.environment["uv"]["command"][-1] == "<generated-harness>"
    packages = {
        package["name"].lower(): package["version"] for package in result.environment["packages"]
    }
    assert "pillow" in packages
    assert result.environment["environment_variables"] == {
        "HF_TOKEN": "<redacted>",
        "TORCH_ALLOW_TF32_CUBLAS_OVERRIDE": "1",
    }
    assert result.environment["project_lock"]["used_by_script_environment"] is False
    environment_path = config.cache_dir / "runs" / "basics-plot" / "environment.json"
    assert json.loads(environment_path.read_text(encoding="utf-8")) == result.environment
    assert any(event.get("duration") is not None for event in result.events)
    page = tmp_path / "docs" / "gallery" / "basics" / "plot.md"
    page_text = page.read_text(encoding="utf-8")
    assert "cell output" in page_text
    assert "progress written to stderr" in page_text
    assert '<details class="e2sg-output" open>' in page_text
    assert "Console output" in page_text
    assert "Standard error" not in page_text
    assert "Download Jupyter notebook" in page_text
    assert 'href="../../_assets/basics-plot/plot.py"' in page_text
    assert 'href="../../_assets/basics-plot/plot.ipynb"' in page_text
    assert "Runtime telemetry" in page_text
    assert "Profiled phases" in page_text
    assert '<details class="e2sg-telemetry-region" open>' in page_text
    assert "Network received" in page_text
    assert (tmp_path / "docs" / "gallery" / "_assets" / "basics-plot" / "thumbnail.webp").exists()
    gallery_css = (
        tmp_path / "docs" / "assets" / "stylesheets" / "earth2studio-gallery.css"
    ).read_text(encoding="utf-8")
    assert '[data-md-color-scheme="default"] .highlight' in gallery_css
    assert '[data-md-color-scheme="slate"] .highlight' in gallery_css
    assert "--md-code-hl-keyword-color" in gallery_css
    assert "--e2sg-download-button-color: #123456" in gallery_css
    assert "--e2sg-output-max-height: 321px" in gallery_css
    assert "background: var(--e2sg-download-button-color" in gallery_css
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
    notebook_environment = notebook["metadata"]["earth2studio_gallery"]["environment"]
    assert notebook_environment["packages"] == result.environment["packages"]
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

    default_config = GalleryConfig.load(tmp_path / "empty-project")
    assert default_config.output_open is False
    assert default_config.output_max_height == 400

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
    assert 'class="e2sg-card-placeholder-icon"><svg' in rebuilt_gallery
    assert ">PY</span>" not in rebuilt_gallery


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


def test_console_output_cleans_control_codes_and_only_styles_failures() -> None:
    console = _event_console(
        {
            "output": "first\x1b[32m green\x1b[0m\rprogress complete\n",
            "stdout": "ignored when combined output is available",
        }
    )
    assert console == "first green\nprogress complete"

    rendered = _console_output(console + "\n<failure>", failed=True, open_by_default=False)
    assert 'class="e2sg-output e2sg-output--error"' in rendered
    assert " open" not in rendered
    assert "Error output" in rendered
    assert "&lt;failure&gt;" in rendered
