# %%
"""
Plot a Sine Wave
================

Use an example-specific UV dependency and let the runner capture a Matplotlib figure.
"""

# /// script
# dependencies = [
#   "earth2studio-gallery @ git+https://github.com/NickGeneva/earth2studio-gallery.git",
#   "matplotlib>=3.10",
#   "numpy>=2.2",
# ]
# ///

# %%
# Create the plot
# ---------------
# If a code cell leaves a Matplotlib figure open without saving it, the execution harness
# saves and closes the figure automatically.

# %% tags=["e2sg-profile:setup"]
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 2 * np.pi, 256)

# %% tags=["e2sg-profile:inference"]
y = np.sin(x)

# %% tags=["e2sg-profile:plotting"]
figure, axis = plt.subplots(figsize=(9, 4.5))
axis.plot(x, y, color="#76b900", linewidth=3)
axis.axhline(0, color="#666666", linewidth=1)
axis.set(xlabel="x", ylabel="sin(x)", title="Automatically captured figure")
axis.grid(alpha=0.2)
figure.tight_layout()
