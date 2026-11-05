"""Save full-page screenshots of a page for the visual audit and for before/after comparison.

    python3 snapshot.py TARGET [--out slopscope-report/shots] [--viewports 375,1280] [--themes light,dark]
                               [--click SELECTOR ...] [--wait MS]

Writes <out>/<viewport>-<theme>.png, plus <viewport>-<theme>-partNN.png pieces one
screen tall when the page is long, because a very tall image shrinks to an unreadable
strip when viewed whole. Dark is skipped when the page looks the same in dark.
TARGET is a URL or a local HTML file. Animations are paused at their start so two
runs of an unchanged page match.
"""
import argparse
import io
import pathlib
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

from slopscope_page import launch, open_page, resolve_themes

PART_HEIGHT = 900   # one screen, the viewport height open_page uses
MAX_PARTS = 12


def split(png, out, stem):
    image = Image.open(io.BytesIO(png))
    if image.height <= PART_HEIGHT * 1.5:
        return []
    written = []
    for n, top in enumerate(range(0, image.height, PART_HEIGHT)):
        if n >= MAX_PARTS:
            break
        path = out / f'{stem}-part{n + 1:02d}.png'
        image.crop((0, top, image.width, min(image.height, top + PART_HEIGHT))).save(path)
        written.append(path)
    return written


def snapshot(target, out, viewports=(375, 1280), themes=('light', 'dark'), clicks=(), wait_ms=0, parts=True):
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    written, notes = [], []
    load = {'clicks': clicks, 'wait_ms': wait_ms}
    with sync_playwright() as p:
        browser = launch(p)
        themes, dark = resolve_themes(browser, target, min(viewports), themes, **load)
        if dark is False:
            notes.append('the page ignores prefers-color-scheme: dark, so no dark screenshots were taken')
        for viewport in viewports:
            for theme in themes:
                page, info = open_page(browser, target, viewport, theme, **load)
                notes += [w for w in info['warnings'] if w not in notes]
                png = page.screenshot(full_page=True)
                path = out / f'{viewport}-{theme}.png'
                path.write_bytes(png)
                written.append(path)
                if parts:
                    written += split(png, out, f'{viewport}-{theme}')
                page.close()
        browser.close()
    return written, notes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('target')
    parser.add_argument('--out', default='slopscope-report/shots')
    parser.add_argument('--viewports', default='375,1280')
    parser.add_argument('--themes', default='light,dark')
    parser.add_argument('--click', action='append', default=[], metavar='SELECTOR',
                        help='click this before the screenshot (e.g. a cookie banner button); repeatable')
    parser.add_argument('--wait', type=int, default=0, metavar='MS', help='extra wait after loading')
    args = parser.parse_args(argv)
    written, notes = snapshot(args.target, args.out, tuple(int(v) for v in args.viewports.split(',')),
                              tuple(args.themes.split(',')), tuple(args.click), args.wait)
    for note in notes:
        print('note:', note)
    for path in written:
        print('wrote', path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
