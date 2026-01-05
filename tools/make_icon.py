"""Convert assets/aura_nexus.png to assets/aura_nexus.ico with multi-size.

Requires Pillow: pip install pillow
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    try:
        from PIL import Image
    except Exception:
        print("Please install Pillow: python -m pip install pillow", file=sys.stderr)
        return 1

    here = os.path.dirname(os.path.abspath(__file__))
    assets = os.path.join(os.path.dirname(here), "assets")
    png = os.path.join(assets, "aura_nexus.png")
    ico = os.path.join(assets, "aura_nexus.ico")

    if not os.path.exists(png):
        print(f"Missing image: {png}")
        return 1

    img = Image.open(png).convert("RGBA")
    # Prepare icon sizes commonly used by Windows
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    resized = [img.resize(s, Image.LANCZOS) for s in sizes]
    # Save ICO with multiple sizes embedded
    resized[0].save(ico, sizes=sizes)
    print(f"Wrote: {ico}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
