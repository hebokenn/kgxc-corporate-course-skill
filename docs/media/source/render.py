#!/usr/bin/env python3
"""Render the README cover and capture the checked-in example courseware.

Run with the installed course media Python (Playwright required).
Uses local, checked-in source assets. Never modifies a course or approval.
"""
import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MEDIA = ROOT / 'docs/media'
settings_file = Path(os.environ.get('COURSE_CONFIG_DIR', Path.home() / '.config/corporate-training-motion')) / 'tools.json'
settings = json.loads(settings_file.read_text()) if settings_file.is_file() else {}
if settings.get('browser_path'):
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = settings['browser_path']

from playwright.sync_api import sync_playwright


def ready(page):
    page.evaluate('document.fonts.ready')
    page.wait_for_function('Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbench', help='Optional running v5 example editor URL for a fresh screenshot')
    args = parser.parse_args()
    with sync_playwright() as playwright:
        options = {'headless': True}
        if settings.get('browser_channel') and settings['browser_channel'] != 'chromium':
            options['channel'] = settings['browser_channel']
        browser = playwright.chromium.launch(**options)
        page = browser.new_page(viewport={'width': 1280, 'height': 640}, device_scale_factor=1)
        if args.workbench:
            page.set_viewport_size({'width': 1600, 'height': 1080})
            page.goto(args.workbench)
            page.get_by_role('button', name=re.compile('核对SN与外包装')).click()
            page.get_by_role('button', name='再检查商品SN编码和外包装', exact=True).click()
            slider = page.get_by_role('slider', name='播放位置', exact=True)
            for index in range(36):
                slider.press('ArrowRight')
            page.get_by_text('00:03.20', exact=True).wait_for()
            page.get_by_role('slider', name='缩放', exact=True).press('Home')
            page.get_by_text('视频、字幕与工程包已生成', exact=True).wait_for(state='hidden')
            page.screenshot(path=str(MEDIA / 'v5-editor.png'))
            page.set_viewport_size({'width': 1280, 'height': 640})
        page.goto((MEDIA / 'source/hero.html').as_uri())
        ready(page)
        page.screenshot(path=str(MEDIA / 'hero.png'))
        page.set_viewport_size({'width': 1280, 'height': 720})
        page.goto((MEDIA / 'courseware-demo.html').as_uri())
        page.get_by_text('1 / 6', exact=True).wait_for()
        page.screenshot(path=str(MEDIA / 'courseware-cover.png'))
        for index in range(3):
            page.get_by_role('button', name='下一页', exact=True).click()
        page.get_by_text('4 / 6', exact=True).wait_for()
        page.screenshot(path=str(MEDIA / 'courseware-overview.png'))
        page.get_by_role('button', name='下一页', exact=True).click()
        page.get_by_text('5 / 6', exact=True).wait_for()
        page.screenshot(path=str(MEDIA / 'courseware-exercise.png'))
        for name in ['flat-mg', 'iso-diorama']:
            page.set_viewport_size({'width': 1280, 'height': 720})
            page.goto((MEDIA / 'styles' / (name + '-preview.svg')).as_uri())
            page.screenshot(path=str(MEDIA / 'styles' / (name + '-preview.png')))
        browser.close()
    print('Rendered cover, actual courseware pages, and original SVG style previews.')


if __name__ == '__main__':
    main()
