# Configuration

Project defaults can be placed in `pyproject.toml`:

```toml
[tool.earth2studio-gallery]
examples_dir = "docs/examples"
docs_dir = "docs"
output_dir = "docs/gallery"
cache_dir = ".e2sgallery"
execute = "stale"
jobs = 1
fail_fast = true
optimize_images = true
image_max_width = 2400
image_max_height = 1600
image_quality = 85
image_min_bytes = 131072
generate_notebooks = true
collect_telemetry = false
telemetry_interval = 1.0

[tool.earth2studio-gallery.runner]
timeout = 7200
uv_args = ["--no-progress"]
```

| Setting | Purpose |
| --- | --- |
| `execute` | `stale`, `always`, or `never` execution policy |
| `jobs` | Concurrent examples; keep at `1` for a single GPU |
| `timeout` | Maximum seconds for each example |
| `python` | UV Python request for examples without their own constraint |
| `extra_dependencies` | Dependencies layered onto inherited example metadata |
| `uv_args` | Additional arguments passed to `uv run` |
| `env` | Environment variables supplied to the example process |
| `optimize_images` | Convert large raster outputs to WebP for the published site |
| `image_max_width` | Maximum width of a published raster image |
| `image_max_height` | Maximum height of a published raster image |
| `image_quality` | WebP quality from 1 to 100 |
| `image_min_bytes` | Minimum source size to optimize, unless dimensions exceed the limits |
| `generate_notebooks` | Generate downloadable `.ipynb` files with captured outputs |
| `collect_telemetry` | Add an execution profile with resource and hardware telemetry |
| `telemetry_interval` | Resource sampling interval in seconds (minimum `0.25`) |

PEP 723 metadata remains the primary dependency declaration for each example. Directory
and sidecar configuration is intended for infrastructure details such as GPU assignment,
cache locations, and timeouts.

Original captured files remain unchanged in `.e2sgallery/`. Optimization only affects
the assets copied into the Zensical or MkDocs site. SVG files and animated GIFs are preserved in
their original formats.

## Runtime telemetry

Telemetry is opt-in because resource sampling adds a small amount of runtime overhead and
publishes hardware details. When enabled, every executed example records wall-clock and
per-cell timings, process-tree CPU and memory use, and a limited system profile. On NVIDIA
systems, GPU utilization, memory, power, model, and driver information are collected with
`nvidia-smi`.

The generated page shows KPI cards, compact resource traces, cell timing bars, and the
execution environment. It never records the hostname or user name. GPU measurements are
device-level measurements, so unrelated work on a shared GPU can affect them. Process CPU
usage may exceed 100% when the example uses multiple cores.

## Gallery card sizing

Gallery cards use a responsive fixed-width grid so a section with only one example does not
stretch its thumbnail across the content area. The default card width is `12rem`, reduced to
`10rem` below the mobile breakpoint. Override either CSS custom property in an additional
stylesheet when a site needs a different density:

```css
:root {
  --e2sg-gallery-card-width: 11rem;
  --e2sg-gallery-card-mobile-width: 9rem;
}
```

The displayed card size is independent of the generated thumbnail asset. Thumbnails remain
720×480 WebP images so they stay sharp on high-density displays while loading efficiently.

## Syntax highlighting

Generated source cells use Pygments through `pymdownx.highlight`. The gallery stylesheet
provides higher-contrast light and dark palettes using Zensical and Material's supported
`--md-code-*` variables. Projects can override individual token colors in a stylesheet loaded
after `earth2studio-gallery.css`, for example:

```css
[data-md-color-scheme="slate"] .highlight {
  --md-code-hl-string-color: #a5d6ff;
  --md-code-hl-keyword-color: #ff7b72;
}
```
