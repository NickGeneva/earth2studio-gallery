# Earth2Studio Gallery

[![CI](https://github.com/NickGeneva/earth2studio-gallery/actions/workflows/ci.yml/badge.svg)](https://github.com/NickGeneva/earth2studio-gallery/actions/workflows/ci.yml)
[![Documentation](https://github.com/NickGeneva/earth2studio-gallery/actions/workflows/docs.yml/badge.svg)](https://nickgeneva.github.io/earth2studio-gallery/)

`earth2studio-gallery` turns Jupytext percent-format Python examples into an
executable Zensical or MkDocs Material gallery. It is deliberately independent of
Sphinx. Zensical is the default documentation backend; the MkDocs plugin remains
available for existing projects.

Each example is executed with `uv run --script`, so its
[PEP 723 inline metadata](https://docs.astral.sh/uv/guides/scripts/) defines a
small, cached environment of its own. This is a good fit for GPU examples whose
models and optional dependencies differ substantially.

## Highlights

- Sphinx-Gallery-style `# %%` scripts and narrative docstrings/comments
- Sphinx-style Python API roles linked through mkdocstrings/autorefs
- opt-in explicit API backreferences with Material example cards
- per-example UV environments, Python versions, environment variables, and timeouts
- content-addressed successful-run cache; unchanged GPU examples do not rerun
- zero-execution full-gallery rendering from retained results
- individual, section, glob, and full-gallery selection
- ordered, scrollable console output plus cell-level errors and generated images
- phase-aware runtime, GPU, CPU, memory, and host-network telemetry
- fast Pillow thumbnail generation and native lazy-loaded Material cards
- Zensical-first standalone CLI plus a compatible MkDocs plugin
- no Sphinx, Jupyter, notebook kernel, or docutils dependency

## Install and try

```console
uv add --dev "earth2studio-gallery @ git+https://github.com/NickGeneva/earth2studio-gallery.git"
uv run e2s-gallery list
uv run e2s-gallery build 01_getting_started
uv run e2s-gallery build 01_getting_started/01_deterministic_workflow.py
uv run e2s-gallery build "03_downscaling/*corrdiff*"
uv run e2s-gallery render
uv run zensical serve
```

The default paths are `examples/`, `docs/`, `docs/gallery/`, and `.e2sgallery/`.
Selectors can be a section directory, an exact path (with or without `.py`), a
unique filename stem, or a glob.

## Zensical configuration

Zensical can read an existing `mkdocs.yml`, which is currently the recommended migration
path for Material projects:

```yaml
theme:
  name: material

plugins:
  - search
  - earth2studio-gallery:
      examples_dir: examples
      output_dir: gallery
      execute: stale       # stale | always | never
      jobs: 1              # safe default for a single GPU
      backreferences: true # index explicit narrative API links
      output_open: false   # expand console output by default
      output_max_height: 400  # scroll after this many CSS pixels
      download_button_color: "#76b900"

extra_css:
  - assets/stylesheets/earth2studio-gallery.css

markdown_extensions:
  - attr_list
  - md_in_html
  - pymdownx.details
  - pymdownx.highlight:
      anchor_linenums: true
      line_spans: __span
      pygments_lang_class: true
  - pymdownx.inlinehilite
  - pymdownx.superfences
```

Zensical does not yet provide a public API for third-party modules. It accepts this shared
configuration but does not invoke the gallery's MkDocs plugin hook, so run the standalone
gallery command before the Zensical backend. The explicit `extra_css` entry is also required
because that hook normally registers the generated gallery stylesheet:

```console
uv run e2s-gallery build       # GPU worker: execute stale examples and render
uv run e2s-gallery render      # CPU/docs worker: render retained outputs only
uv run zensical build
uv run zensical serve
```

The generated pages are ordinary Markdown and compatible HTML, so no Zensical-specific
rendering layer is required. The repository tests the same generated gallery with both
Zensical and MkDocs.

## MkDocs compatibility

Existing MkDocs projects can continue to use the plugin configuration above. MkDocs invokes
the gallery automatically during `mkdocs build` or `mkdocs serve`:

```console
uv run mkdocs build --strict
uv run mkdocs serve
```

`execute: stale` reuses a successful run when the script and its runner settings
have not changed. For CI, a useful split is to execute selected examples on GPU
workers, retain `.e2sgallery/`, and run `e2s-gallery render` followed by Zensical on a
CPU documentation worker.

`e2s-gallery render` reconstructs the entire generated gallery from `.e2sgallery` without
executing examples. Retained cards are marked `Cached`, `Stale`, or `Missing` by comparing the
current content fingerprint, not the repository commit.

## Per-example settings

An example's PEP 723 block is its dependency environment:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "earth2studio[dlwp] @ git+https://github.com/NVIDIA/earth2studio.git",
#   "cartopy",
# ]
# ///
```

Optional `_gallery.toml` files are inherited down the examples tree. A
`name.gallery.toml` file applies only to `name.py`:

```toml
[runner]
python = "3.12"
timeout = 14400
extra_dependencies = ["nvidia-ml-py>=13"]
uv_args = ["--no-progress"]

[runner.env]
CUDA_VISIBLE_DEVICES = "0"
EARTH2STUDIO_CACHE = "/scratch/earth2studio"
```

Root defaults can live in `gallery.toml` under `[gallery]` and
`[gallery.runner]`, or in `pyproject.toml` under
`[tool.earth2studio-gallery]` and `[tool.earth2studio-gallery.runner]`.

## Authoring format

The parser accepts the current Earth2Studio example style: Jupytext `# %%`
cells, an opening reStructuredText-style docstring, narrative comment cells,
Python code cells, common Python roles, and `literalinclude`. Generated pages are
plain Markdown plus Material-compatible HTML cards, so Zensical or MkDocs owns the final
HTML.

With `backreferences: true`, native Markdown/autorefs links such as
``[`deterministic`][earth2studio.run.deterministic]`` and legacy roles such as
``:func:`~earth2studio.run.deterministic``` are indexed from narrative cells only. Put
`<!-- e2sg-backreferences: earth2studio.run.deterministic -->` on the API page where its
example cards should appear. Python imports and calls are never inferred.

The repository contains a self-hosting documentation project under `docs/`. Its small
numbered examples install the package from this Git repository, and the documentation
workflow publishes the rendered site to
[GitHub Pages](https://nickgeneva.github.io/earth2studio-gallery/).
