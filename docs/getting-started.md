# Getting started

## Install from Git

Create a documentation project and add the package directly from GitHub:

```console
uv init
uv add --dev "earth2studio-gallery @ git+https://github.com/NickGeneva/earth2studio-gallery.git"
```

Create `mkdocs.yml`:

```yaml
site_name: My example gallery
theme:
  name: material
plugins:
  - search
  - earth2studio-gallery:
      examples_dir: examples
      output_dir: gallery
      execute: never
markdown_extensions:
  - attr_list
  - md_in_html
  - pymdownx.details
  - pymdownx.superfences
```

Keeping `execute: never` makes the expensive execution phase explicit. Execute examples on
the GPU worker, then recreate the complete gallery without execution before MkDocs runs:

```console
uv run e2s-gallery build
uv run e2s-gallery render
uv run mkdocs serve
```

`render` discovers every example and reconstructs its Markdown page, optimized assets,
downloadable notebook, telemetry panel, CSS, and the combined index from `.e2sgallery`. It
never starts an example process or resolves an example environment.

## Select what runs

```console
# One numbered section
uv run e2s-gallery build 01_getting_started

# One example
uv run e2s-gallery build 01_getting_started/01_minimal_image.py

# A glob
uv run e2s-gallery build "02_plotting/*sine*"
```

UV caches the environment described by each script, while Earth2Studio Gallery caches
the successful run artifacts. Repeating either command avoids unnecessary setup and
execution.

## Understand result status

Gallery cards distinguish retained results using content fingerprints:

- **Cached**: the retained run matches the current script and resolved runner settings.
- **Stale**: retained output exists, but the script or runner settings have changed.
- **Missing**: no successful retained execution exists for the example.

The fingerprint is independent of the Git commit. Unrelated commits therefore do not make an
example stale.

## Follow execution progress

The build command reports each example's lifecycle as it happens: cache lookup, harness
preparation, UV environment resolution, execution, output capture, Markdown rendering,
and image optimization. Examples that run longer than 30 seconds emit periodic elapsed-
time heartbeats, so a quiet GPU workload does not look stalled.

```text
18:50:10  EXECUTE    02_plotting/01_sine_wave.py
                     UV resolving environment and running (timeout 7200s)
18:50:11  CAPTURE    02_plotting/01_sine_wave.py
                     collected 1 image artifact(s)
18:50:11  IMAGE      02_plotting/01_sine_wave.py
                     kept 001-cell-2.png (33.9 KiB; below limits)
```

The MkDocs plugin reports the same stages through MkDocs' logging system.
