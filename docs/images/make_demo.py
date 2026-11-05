"""Make docs/images/demo.png: a real slopscope run on the fictional examples/sloppy.html.

    python3 docs/images/make_demo.py

Left: the page at 375px (snapshot.py). Right: what measure.py found. Needs the same
packages as the skill (see skills/slopscope/requirements.txt); CHROMIUM_PATH works too.
"""
import html
import re
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'skills' / 'slopscope' / 'scripts'))
import measure  # noqa: E402
import snapshot  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from slopscope_page import launch  # noqa: E402

LABELS = {  # short Japanese names for the checks
    'M-01': '文字のコントラスト', 'M-02': '選んだときの枠', 'M-03': '枠の欠け', 'M-04': '横のはみ出し',
    'M-05': 'iPhone の拡大', 'M-06': '名前のない部品', 'M-07': '押す大きさ', 'M-08': '動きを減らす設定',
}


def value(check):
    f = check['findings'][0]
    if 'value' in f:
        return f"{f['value']}（基準 {f['needs']}）"
    if 'clipped_by' in f:
        return '親に切られている'
    if 'pixels_changed' in f:
        return '選んでも何も変わらない'
    if 'overflow_px' in f:
        return f"+{f['overflow_px']}px"
    if 'font_px' in f:
        return f"{f['font_px']:g}px（16px 未満）"
    if 'size' in f:
        return f"{f['size'][0]}×{f['size'][1]}px"
    if 'role' in f:
        return f"{f['role']} に名前がない"
    return f.get('name', '')


def short(selector):
    """The last two steps of a selector, without :nth-of-type, to fit one line."""
    return ' > '.join(re.sub(r':nth-of-type\(\d+\)', '', part) for part in selector.split(' > ')[-2:])


def main():
    sample = ROOT / 'examples' / 'sloppy.html'
    with tempfile.TemporaryDirectory() as tmp:
        shots, _ = snapshot.snapshot(str(sample), pathlib.Path(tmp), (375,), ('light',), parts=False)
        data = measure.measure(str(sample), (375,), ('light',))
        rows = ''.join(
            f'<tr><td class="id">{c["id"]}</td><td>{LABELS[c["id"]]}</td>'
            f'<td class="v">{html.escape(value(c))}</td><td class="sel">{html.escape(short(c["findings"][0]["selector"]))}</td></tr>'
            for c in data['checks'] if c['status'] == 'fail')
        page = f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>slopscope demo</title><style>
  body{{margin:0;width:1280px;height:720px;background:#F4F4F5;font-family:"Noto Sans CJK JP",sans-serif;color:#18181B;
       display:grid;grid-template-columns:420px minmax(0,1fr);gap:40px;padding:48px;box-sizing:border-box}}
  h2{{margin:0 0 16px;font-size:22px}} h2 span{{font-weight:400;color:#52525B;font-size:16px;margin-left:8px}}
  .phone{{background:#fff;border:1px solid #D4D4D8;border-radius:24px;overflow:hidden;height:560px}}
  .phone img{{width:100%;display:block}}
  .panel{{background:#18181B;color:#F4F4F5;border-radius:16px;padding:28px 32px;font-size:17px}}
  .cmd{{font-family:"DejaVu Sans Mono",monospace;font-size:15px;color:#A1A1AA;margin-bottom:18px}}
  table{{border-collapse:collapse;width:100%}} td{{padding:10px 8px;border-top:1px solid #3F3F46;white-space:nowrap}}
  .id{{font-family:"DejaVu Sans Mono",monospace;color:#FF7A5C;font-weight:700;width:64px}}
  .v{{font-weight:700}} .sel{{font-family:"DejaVu Sans Mono",monospace;font-size:13px;color:#A1A1AA;white-space:normal}}
  .note{{margin-top:16px;color:#A1A1AA;font-size:15px}}
</style></head><body>
  <div><h2>見た目<span>架空の見本ページ・幅 375px</span></h2><div class="phone"><img src="{shots[0].as_uri()}" alt=""></div></div>
  <div><h2>計測<span>Chromium で開いて数字で見る</span></h2><div class="panel">
    <div class="cmd">$ python3 scripts/measure.py examples/sloppy.html</div>
    <table>{rows}</table>
    <div class="note">8 項目すべて不合格。直したあとは compare.py で前後を比べる。</div></div></div>
</body></html>'''
        doc = pathlib.Path(tmp, 'demo.html'); doc.write_text(page)
        out = ROOT / 'docs' / 'images' / 'demo.png'
        with sync_playwright() as p:
            browser = launch(p)
            pg = browser.new_page(viewport={'width': 1280, 'height': 720}, device_scale_factor=1.5)
            pg.goto(doc.as_uri()); pg.wait_for_timeout(300)
            pg.screenshot(path=str(out))
            browser.close()
    print('wrote', out)


if __name__ == '__main__':
    main()
