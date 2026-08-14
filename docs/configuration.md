# Configuration

Project defaults can be placed in `pyproject.toml`:

```toml
[tool.earth2studio-gallery]
examples_dir = "docs/examples"
docs_dir = "docs"
output_dir = "docs/gallery"
cache_dir = ".e2sgallery"
cache_output_directory = false
execute = "stale"
jobs = 1
fail_fast = true
optimize_images = true
image_max_width = 2400
image_max_height = 1600
image_quality = 85
image_min_bytes = 131072
generate_notebooks = true
backreferences = false
output_open = false
output_max_height = 400
download_button_color = "#76b900"
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
| `environment` | Execution mode for examples: `isolated` (default) or `project` |
| `extras` | Project extras expected in an already-synchronized project environment |
| `groups` | Dependency groups expected in an already-synchronized project environment |
| `python` | UV Python request for examples without their own constraint |
| `extra_dependencies` | Dependencies layered onto inherited example metadata |
| `uv_args` | Additional arguments passed to `uv run` |
| `env` | Environment variables supplied to the example process |
| `cache_output_directory` | Retain the complete execution output directory; defaults to `false` |
| `optimize_images` | Convert large raster outputs to WebP for the published site |
| `image_max_width` | Maximum width of a published raster image |
| `image_max_height` | Maximum height of a published raster image |
| `image_quality` | WebP quality from 1 to 100 |
| `image_min_bytes` | Minimum source size to optimize, unless dimensions exceed the limits |
| `generate_notebooks` | Generate clean, unexecuted `.ipynb` downloads without embedded outputs |
| `backreferences` | Index explicit narrative API links and add example cards at API markers |
| `output_open` | Expand captured console output by default; defaults to `false` |
| `output_max_height` | Maximum expanded console height in pixels; defaults to `400` |
| `download_button_color` | CSS color for download buttons; defaults to the theme accent |
| `collect_telemetry` | Add an execution profile with resource and hardware telemetry |
| `telemetry_interval` | Resource sampling interval in seconds (minimum `0.25`) |

Values configured through `runner.env` are passed to UV and the example process but are never
included in retained provenance, manifests, generated Markdown, or downloadable notebook
metadata.

Each example runs from `.e2sgallery/runs/<example>/outputs/`, so relative paths created by the
script are isolated from the source tree. With the default `cache_output_directory = false`,
the gallery copies renderable images into `artifacts/` and then deletes that execution output
directory. Console output, telemetry, manifests, and provenance are retained separately. Set
the option to `true` to keep all generated files for debugging or downstream reuse. Files an
example writes to an absolute path outside its working directory are never managed by the
gallery.

For Zensical and standalone CLI builds, configure these values under
`[tool.earth2studio-gallery]` or `[gallery]`. MkDocs builds may set the same values under the
`earth2studio-gallery` plugin. Because Zensical does not execute that plugin hook, values that
exist only in `mkdocs.yml` do not configure the standalone command.

When backreferences are enabled, generate API Markdown before running the gallery command.
Each API object needs a `<!-- e2sg-backreferences: package.object -->` marker. The registry
is written to `.e2sgallery/backreferences.json`; disabling the option removes previously
managed cards while preserving author markers.

PEP 723 metadata remains the primary dependency declaration for each example. Directory
and sidecar configuration is intended for infrastructure details such as GPU assignment,
cache locations, and timeouts.

## Project execution environments

Examples use an isolated PEP 723 environment by default. This lets examples select different
Python versions and incompatible dependency sets without changing the documentation project's
environment.

To reuse the repository's existing UV project environment for every example, set the default in
the parent `pyproject.toml`:

```toml
[tool.earth2studio-gallery.runner]
environment = "project"
extras = ["data", "stormcast-conus"]
groups = ["docs"]
```

The same `[runner]` keys work in `gallery.toml`. An individual example can override the project
default—or opt into project mode when the default is isolated—using its inline metadata:

```python
# /// script
# dependencies = [
#   "earth2studio[data,stormcast-conus] @ git+https://github.com/NVIDIA/earth2studio.git",
#   "cartopy",
# ]
#
# [tool.earth2studio-gallery]
# environment = "project"
# ///
```

`environment = "project"` requires `pyproject.toml` and `uv.lock` at the gallery root. The
gallery verifies `uv lock --check`, finds the project environment with `uv run --project`, and
runs the generated harness with `--no-sync`. Because the harness is passed to `python` instead
of to `uv run --script`, UV does not create or resolve a PEP 723 environment. The project must
already be synchronized with every dependency required by the example.

Extras on the dependency whose normalized name matches `[project].name` are inferred for each
example. In the example above, those are `data` and `stormcast-conus`. Additional project extras
and dependency groups can be declared in the parent runner configuration or inline:

```python
# [tool.earth2studio-gallery]
# environment = "project"
# extras = ["perturbation"]
# groups = ["docs"]
```

The gallery validates these names against `[project.optional-dependencies]` and
`[dependency-groups]`, records them in retained execution provenance, and includes the local
lockfile in the execution fingerprint. It does not install the selections. Prepare
the shared environment before building, for example:

```console
uv sync --locked --extra data --extra stormcast-conus --group docs
uv run e2s-gallery build 04_nowcasting/01_stormcast_example.py
```

Use inline `environment = "isolated"` to exempt one example from a project-level default. Omit
both settings to retain the standard isolated behavior. The `python` and `extra_dependencies`
runner settings apply only to isolated environments; `uv_args`, environment variables, and
timeouts apply to both modes.

Original captured files remain unchanged in `.e2sgallery/`. Optimization only affects
the assets copied into the Zensical or MkDocs site. SVG files and animated GIFs are preserved in
their original formats.

The download-button setting accepts a single CSS color such as `#76b900`, `navy`, or
`rgb(118 185 0)`. For stylesheet-level control, override
`--e2sg-download-button-color` after loading `earth2studio-gallery.css`.

## Console output

Standard output, logging, progress bars, warnings, and other standard-error text are merged
in write order into one **Console output** disclosure beneath the corresponding code cell.
The disclosure is closed by default and becomes vertically scrollable after 400 pixels.
Only an actual uncaught exception receives error styling.

Set `output_open = true` to expand every console disclosure initially, and customize
`output_max_height` to change its vertical limit. The same options are available under the
MkDocs plugin configuration.

## Runtime telemetry

Telemetry is opt-in because resource sampling adds a small amount of runtime overhead and
publishes hardware details. When enabled, every executed example records wall-clock and
per-cell timings, process-tree CPU and memory use, and a limited system profile. On NVIDIA
systems, GPU utilization, memory, power, model, and driver information are collected with
`nvidia-smi`.

The generated page shows KPI cards, compact resource traces, cell timing bars, and the
execution environment. It never records the hostname or user name. GPU measurements are
device-level measurements, so unrelated work on a shared GPU can affect them. The CPU load
shown on a page is the example process tree's average and peak share of the system's total
logical CPU capacity, normalized to 0–100%.

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
