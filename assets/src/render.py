"""Render the README images with headless Chrome (Playwright, channel='chrome').

    python3 assets/src/render.py

Writes assets/hero.png (1760x880), assets/hero@2x.png (3520x1760),
assets/logo.png / logo-dark.png (lockup, transparent) and
assets/logo-mark-{light,dark}-{32,512}.png.
"""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

SRC = Path(__file__).resolve().parent
OUT = SRC.parent


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        for scale, name in ((1, "hero.png"), (2, "hero@2x.png")):
            pg = b.new_page(viewport={"width": 1760, "height": 880}, device_scale_factor=scale)
            pg.goto((SRC / "hero.html").as_uri())
            pg.wait_for_selector("body[data-ready='1']", timeout=30000)
            pg.screenshot(path=str(OUT / name), clip={"x": 0, "y": 0, "width": 1760, "height": 880})
            pg.close()
        for mode, name in (("light", "logo.png"), ("dark", "logo-dark.png")):
            pg = b.new_page(viewport={"width": 1000, "height": 300}, device_scale_factor=1)
            pg.goto((SRC / "logo.html").as_uri() + f"?mode={mode}&kind=lockup")
            pg.wait_for_selector("body[data-ready='1']", timeout=30000)
            pg.locator(".lockup").screenshot(path=str(OUT / name), omit_background=True)
            pg.close()
        for mode in ("light", "dark"):
            for size in (32, 512):
                pg = b.new_page(viewport={"width": size, "height": size})
                pg.goto((SRC / "logo.html").as_uri() + f"?mode={mode}&kind=mark&size={size}")
                pg.wait_for_selector("body[data-ready='1']", timeout=30000)
                pg.locator(".mark svg").screenshot(path=str(OUT / f"logo-mark-{mode}-{size}.png"),
                                                   omit_background=True)
                pg.close()
        b.close()
    for f in sorted(OUT.glob("*.png")):
        print(f.name, os.path.getsize(f))


if __name__ == "__main__":
    main()
