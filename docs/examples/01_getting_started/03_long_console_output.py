# %%
"""
Review Long Console Output
==========================

Keep lengthy mixed stdout and stderr logs readable in a scrollable disclosure.
"""

# /// script
# dependencies = [
#   "earth2studio-gallery @ git+https://github.com/NickGeneva/earth2studio-gallery.git",
# ]
# ///

# %%
# Stream a longer log
# -------------------
# Both streams are captured in write order. Text written to stderr is ordinary console output
# unless the cell raises an exception.

# %% tags=["e2sg-profile:inference"]
import sys

for step in range(1, 121):
    print(f"step {step:03d}/120 · processing forecast batch")
    if step % 15 == 0:
        print(f"checkpoint {step:03d} written", file=sys.stderr)

print("processing complete")
