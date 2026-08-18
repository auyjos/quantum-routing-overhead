"""Render the A0 poster, fitting the layout scale to exactly one page.

Binary-searches the `--k` multiplier for the largest value whose rendered height still
fits 1189 mm. Hand-tuning sizes would silently break the moment any figure is replaced by
one with a different aspect ratio; this measures instead.
"""
import pathlib

from playwright.sync_api import sync_playwright

A0_W_PX, A0_H_PX = 3179, 4494          # 841 x 1189 mm at 96 dpi
URL = "file://" + str(pathlib.Path("poster_a0.html").resolve())


def height_at(page, k):
    page.evaluate(f"document.documentElement.style.setProperty('--k', '{k}')")
    page.wait_for_timeout(220)
    return page.evaluate(
        "document.body.getBoundingClientRect().height"
        " + parseFloat(getComputedStyle(document.body).paddingBottom)"
    )


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": A0_W_PX, "height": A0_H_PX})
    page.goto(URL)
    page.wait_for_timeout(3500)          # webfonts must settle before measuring

    lo, hi = 0.40, 1.00
    print(f"unscaled height {height_at(page, 1.0):.0f}px vs page {A0_H_PX}px")
    for _ in range(18):
        mid = (lo + hi) / 2
        if height_at(page, mid) <= A0_H_PX:
            lo = mid
        else:
            hi = mid
    k = round(lo, 4)
    final = height_at(page, k)
    print(f"fitted --k = {k}  ->  {final:.0f}px of {A0_H_PX}px "
          f"({100 * final / A0_H_PX:.1f}% of the page)")

    page.pdf(path="quantum-routing-overhead-poster-a0-portrait.pdf",
             width="841mm", height="1189mm", print_background=True,
             prefer_css_page_size=True)
    page.screenshot(path="poster_preview.png", full_page=True)
    browser.close()

pathlib.Path("poster_scale.txt").write_text(f"{k}\n", encoding="utf-8")
print("wrote quantum-routing-overhead-poster-a0-portrait.pdf and poster_preview.png")
