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
# unless the cell raises an exception. The ensemble diagnostic is intentionally wider than the
# page so this example also exercises horizontal scrolling.

# %% tags=["e2sg-profile:inference"]
import sys

members = " | ".join(f"member_{index:02d}=ready" for index in range(32))
print(f"ensemble diagnostic · {members}")

for step in range(1, 121):
    print(f"step {step:03d}/120 · processing forecast batch")
    if step % 15 == 0:
        print(f"checkpoint {step:03d} written", file=sys.stderr)

print("processing complete")
