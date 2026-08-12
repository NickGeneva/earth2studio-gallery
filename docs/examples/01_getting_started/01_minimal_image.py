# %%
"""
Create a Minimal Image
======================

Create a small gallery example with only the package's built-in Pillow dependency.
"""

# /// script
# dependencies = [
#   "earth2studio-gallery @ git+https://github.com/NickGeneva/earth2studio-gallery.git",
# ]
# ///

# %%
# Import the package
# ------------------
# Importing the version demonstrates that this isolated example environment installed
# Earth2Studio Gallery directly from its Git repository.
# Project-wide behavior is configured with
# [`GalleryConfig`][earth2studio_gallery.config.GalleryConfig].

# %% tags=["e2sg-profile:setup"]
from pathlib import Path

from PIL import Image, ImageDraw

from earth2studio_gallery import __version__

print(f"Running with earth2studio-gallery {__version__}")

# %%
# Draw and save an image
# ----------------------
# Any new PNG, JPEG, WebP, GIF, or SVG file is collected after the cell completes.

# %% tags=["e2sg-profile:plotting"]
output = Path("outputs")
output.mkdir(exist_ok=True)

image = Image.new("RGB", (960, 540), "#101820")
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((90, 90, 870, 450), radius=36, fill="#76b900")
draw.text((180, 250), "UV environment → Python → MkDocs", fill="black")
image.save(output / "minimal-gallery.png")
