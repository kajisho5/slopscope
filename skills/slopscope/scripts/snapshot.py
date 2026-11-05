"""Save full-page screenshots of a page for the visual audit and for before/after comparison.

    python3 snapshot.py TARGET [--out slopscope-report/shots] [--viewports 375,1280] [--themes light,dark]

Writes <out>/<viewport>-<theme>.png. TARGET is a URL or a local HTML file.
Animations are paused at their start so two runs of an unchanged page match.
"""
import argparse
import os
import pathlib
import sys

from playwright.sync_api import sync_playwright


def snapshot(target, out, viewports=(375, 1280), themes=('light', 'dark')):
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    url = target if '://' in target else pathlib.Path(target).resolve().as_uri()
    written = []
    with sync_playwright() as p:
        launch = {'args': ['--no-sandbox']}
        if os.environ.get('CHROMIUM_PATH'):
            launch['executable_path'] = os.environ['CHROMIUM_PATH']
        browser = p.chromium.launch(**launch)
        for viewport in viewports:
            for theme in themes:
                page = browser.new_page(viewport={'width': viewport, 'height': 900}, color_scheme=theme)
                page.goto(url, wait_until='load')
                page.wait_for_timeout(300)
                page.evaluate('document.getAnimations().forEach(a=>{a.pause();a.currentTime=0})')
                path = out / f'{viewport}-{theme}.png'
                page.screenshot(path=str(path), full_page=True)
                written.append(path)
                page.close()
        browser.close()
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('target')
    parser.add_argument('--out', default='slopscope-report/shots')
    parser.add_argument('--viewports', default='375,1280')
    parser.add_argument('--themes', default='light,dark')
    args = parser.parse_args(argv)
    for path in snapshot(args.target, args.out, tuple(int(v) for v in args.viewports.split(',')), tuple(args.themes.split(','))):
        print('wrote', path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
