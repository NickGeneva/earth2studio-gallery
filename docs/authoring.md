# Authoring examples

Examples follow the same numbered-directory style used by Earth2Studio:

```text
docs/examples/
├── 01_getting_started/
│   ├── 01_minimal_image.py
│   └── 02_console_output.py
└── 02_plotting/
    └── 01_sine_wave.py
```

Each script is regular runnable Python in
[Jupytext percent format](https://jupytext.readthedocs.io/en/latest/formats-scripts.html#the-percent-format):

````python
# %%
"""
My Example
==========

A one-paragraph summary used on the gallery card.
"""

# /// script
# dependencies = [
#   "earth2studio-gallery @ git+https://github.com/NickGeneva/earth2studio-gallery.git",
# ]
# ///

# %%
# Create an artifact
# ------------------

# %%
from PIL import Image

Image.new("RGB", (640, 360), "navy").save("example.png")
````

The opening docstring becomes the title and introduction. Comment-only cells become
Markdown, code cells become highlighted Python, printed text becomes an output block,
and created images appear after the cell that produced them.

Each generated page offers two downloads by default: the unchanged Jupytext Python
source and a Jupyter notebook. The notebook contains the converted Markdown and code
cells, PEP 723 environment metadata, captured console streams, and embedded original
images, so it opens with the documented outputs already present.

## Custom execution settings

Place `_gallery.toml` in a section to configure all examples below it:

```toml
[runner]
timeout = 14400

[runner.env]
CUDA_VISIBLE_DEVICES = "0"
EARTH2STUDIO_CACHE = "/scratch/earth2studio"
```

Use `01_example.gallery.toml` beside `01_example.py` for a one-example override.
