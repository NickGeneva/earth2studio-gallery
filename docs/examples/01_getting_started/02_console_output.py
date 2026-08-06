# %%
"""
Capture Console Output
======================

Printed output is associated with the code cell and rendered beneath the source.
"""

# /// script
# dependencies = [
#   "earth2studio-gallery @ git+https://github.com/NickGeneva/earth2studio-gallery.git",
# ]
# ///

# %%
# A computation with visible output
# ---------------------------------

# %%
from earth2studio_gallery import __version__

temperatures = [13.2, 14.8, 17.1, 16.4]
mean_temperature = sum(temperatures) / len(temperatures)

print(f"earth2studio-gallery: {__version__}")
print(f"samples: {len(temperatures)}")
print(f"mean temperature: {mean_temperature:.2f} °C")
