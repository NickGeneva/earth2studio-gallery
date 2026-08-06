# Earth2Studio Gallery

[![CI](https://github.com/NickGeneva/earth2studio-gallery/actions/workflows/ci.yml/badge.svg)](https://github.com/NickGeneva/earth2studio-gallery/actions/workflows/ci.yml)
[![Documentation](https://github.com/NickGeneva/earth2studio-gallery/actions/workflows/docs.yml/badge.svg)](https://nickgeneva.github.io/earth2studio-gallery/)

`earth2studio-gallery` turns Jupytext percent-format Python examples into an
executable MkDocs Material gallery. It is deliberately independent of Sphinx.

Each example is executed with `uv run --script`, so its
[PEP 723 inline metadata](https://docs.astral.sh/uv/guides/scripts/) defines a
small, cached environment of its own. This is a good fit for GPU examples whose
models and optional dependencies differ substantially.

## Highlights

- Sphinx-Gallery-style `# %%` scripts and narrative docstrings/comments
- per-example UV environments, Python versions, environment variables, and timeouts
- content-addressed successful-run cache; unchanged GPU examples do not rerun
- zero-execution full-gallery rendering from retained results
- individual, section, glob, and full-gallery selection
- cell-level standard output, errors, and generated image collection
- fast Pillow thumbnail generation and native lazy-loaded Material cards
- MkDocs plugin plus a standalone CLI for splitting GPU execution from site builds
- no Sphinx, Jupyter, notebook kernel, or docutils dependency

## Install and try

```console
uv add --dev "earth2studio-gallery @ git+https://github.com/NickGeneva/earth2studio-gallery.git"
uv run e2s-gallery list
uv run e2s-gallery build 01_getting_started
uv run e2s-gallery build 01_getting_started/01_deterministic_workflow.py
uv run e2s-gallery build "03_downscaling/*corrdiff*"
uv run e2s-gallery render
uv run mkdocs serve
```

The default paths are `examples/`, `docs/`, `docs/gallery/`, and `.e2sgallery/`.
Selectors can be a section directory, an exact path (with or without `.py`), a
unique filename stem, or a glob.

## MkDocs configuration

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

markdown_extensions:
  - attr_list
  - md_in_html
  - pymdownx.details
  - pymdownx.superfences
```

`execute: stale` reuses a successful run when the script and its runner settings
have not changed. For CI, a useful split is to execute selected examples on GPU
workers, retain `.e2sgallery/`, and run MkDocs with `execute: never` on a CPU
documentation worker.

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
plain Markdown plus Material-compatible HTML cards, so MkDocs owns the final HTML.

The repository contains a self-hosting documentation project under `docs/`. Its small
numbered examples install the package from this Git repository, and the documentation
workflow publishes the rendered site to
[GitHub Pages](https://nickgeneva.github.io/earth2studio-gallery/).
