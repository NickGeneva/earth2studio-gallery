# %%
"""
Profile Workflow Phases
=======================

Separate setup, inference, and plotting telemetry with standard Jupytext cell tags.
"""

# /// script
# dependencies = [
#   "earth2studio-gallery @ git+https://github.com/NickGeneva/earth2studio-gallery.git",
#   "pillow>=11",
# ]
# ///

# %%
# Phase-aware telemetry
# ---------------------
# Cells tagged with ``e2sg-profile:<name>`` receive their own expandable telemetry section.

# %% tags=["e2sg-profile:setup"]
import time

from PIL import Image, ImageDraw

print("Downloading inputs and loading the model")
time.sleep(1.1)

# %% tags=["e2sg-profile:inference"]
print("Running inference")
deadline = time.perf_counter() + 1.2
value = 0
while time.perf_counter() < deadline:
    value = (value + 17) % 104729
print(f"Inference result: {value}")

# %% tags=["e2sg-profile:plotting"]
print("Rendering the forecast")
image = Image.new("RGB", (640, 360), "#101820")
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((80, 80, 560, 280), radius=24, fill="#76b900")
draw.text((210, 165), "Forecast complete", fill="white")
image.save("profiled-workflow.png")
time.sleep(1.1)
