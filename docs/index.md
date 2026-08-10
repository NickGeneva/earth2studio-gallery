# Earth2Studio Gallery

Build fast, executable example galleries for Zensical and MkDocs Material without Sphinx.

Earth2Studio Gallery reads Jupytext percent-format Python scripts, executes each script
inside its own UV environment, captures generated images and console output, and writes
ordinary Markdown pages for Zensical or MkDocs.

<div class="grid cards" markdown>

- :material-rocket-launch: **UV-native execution**

  Every example can declare an independent PEP 723 environment, Python version, timeout,
  and GPU assignment.

- :material-lightning-bolt: **Built for repeat runs**

  Successful executions are content-addressed and reused until source or runner settings
  change.

- :material-image-multiple: **Zensical-native output**

  The generated gallery uses plain Markdown, lazy-loaded image cards, and the current
  Zensical theme, while retaining MkDocs Material compatibility.

- :material-language-python: **No Sphinx dependency**

  Jupytext cells, common Python roles, and `literalinclude` are handled directly.

</div>

[Get started](getting-started.md){ .md-button .md-button--primary }
[Browse the generated examples](gallery/index.md){ .md-button }

## What the documentation demonstrates

This site is self-hosting: the examples under `docs/examples/` install
`earth2studio-gallery` directly from its Git repository using PEP 723 metadata. The
GitHub Pages workflow executes those examples before Zensical builds the site.
