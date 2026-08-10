# Development

The repository uses the same core Python tooling conventions as Earth2Studio: UV for
dependency and lock management, Black for formatting, Ruff for linting, pytest, mypy,
and pre-commit hygiene checks.

```console
uv sync --extra dev
uv run pre-commit install
uv run pre-commit run --all-files
uv run pytest
uv build
```

Build the self-hosting gallery and documentation locally:

```console
uv run e2s-gallery --examples-dir docs/examples build
uv run zensical build
uv run zensical serve
```

The first command executes example environments and retains outputs in `.e2sgallery/`.
Zensical is the default site backend. It consumes the Markdown and assets written by the
standalone gallery command without unexpectedly starting new workloads.

Verify the retained MkDocs backend when changing rendering or CSS:

```console
uv run e2s-gallery --examples-dir docs/examples render
uv run mkdocs build --strict --site-dir site-mkdocs
```

## Automation

The repository has three GitHub Actions workflows:

- `ci.yml` runs formatting, linting, typing, strict Zensical and MkDocs documentation
  builds, distribution building, and tests on Python 3.11 and 3.13.
- `docs.yml` builds the complete site and publishes it with GitHub Pages Actions.
- `publish.yml` builds and validates the wheel and source distribution when a numeric version
  tag such as `0.1.0` is pushed, then publishes through PyPI Trusted Publishing.

Before the first release, configure a PyPI Trusted Publisher for the
`NickGeneva/earth2studio-gallery` repository, `publish.yml` workflow, and `pypi` GitHub
environment. The pushed tag must exactly match the version in `pyproject.toml`.
