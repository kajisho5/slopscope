"""Generate slopscope logo concepts (light + dark) into docs/logo/concepts/."""
import pathlib, sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

OUT = pathlib.Path(sys.argv[1])
INK, ACC = '#18181B', '#FF4F2E'
INK_D, ACC_D = '#F4F4F5', '#FF7A5C'

def svg(view, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" role="img" aria-labelledby="t">'
            f'<title id="t">{title}</title>{body}</svg>\n')

DROP = 'M32 42C32 42 25.5 50 25.5 54a6.5 6.5 0 0 0 13 0C38.5 50 32 42 32 42Z'
def reticle(ink, acc):
    return (f'<g fill="none" stroke="{ink}" stroke-width="6" stroke-linecap="round">'
            f'<circle cx="32" cy="29" r="13"/></g>'
            f'<path d="M32 3v4M6 29h4M54 29h4" stroke="{ink}" stroke-width="5" stroke-linecap="round"/>'
            f'<path d="{DROP}" fill="{acc}"/>')

def halflens(ink, acc):
    return (f'<path d="M27 10A17 17 0 0 0 27 44Z" fill="{ink}"/>'
            f'<circle cx="27" cy="27" r="17" fill="none" stroke="{ink}" stroke-width="5"/>'
            f'<path d="M40 40l16 16" stroke="{acc}" stroke-width="7" stroke-linecap="round"/>')

def sscope(ink, acc):
    return (f'<path d="M40.43 12.93A11 11 0 1 0 32 31A11 11 0 1 1 23.57 49.07" fill="none" '
            f'stroke="{ink}" stroke-width="7" stroke-linecap="round"/>'
            f'<circle cx="32" cy="20" r="3.5" fill="{acc}"/>')

def ruler(ink, acc):
    return (f'<circle cx="27" cy="27" r="18" fill="none" stroke="{ink}" stroke-width="6"/>'
            f'<path d="M19 35v-6M27 35v-12M35 35v-6" stroke="{acc}" stroke-width="4" stroke-linecap="round"/>'
            f'<path d="M41 41l15 15" stroke="{ink}" stroke-width="7" stroke-linecap="round"/>')

# Wordmark: Inter Bold outlines (SIL OFL 1.1), the "o" of "scope" replaced by the reticle.
font = TTFont('/usr/share/fonts/opentype/inter/Inter-Bold.otf')
gs, cmap, upm = font.getGlyphSet(), font.getBestCmap(), font['head'].unitsPerEm
SIZE, BASE = 48, 46
k = SIZE / upm
def glyph(ch, x, fill):
    name = cmap[ord(ch)]
    pen = SVGPathPen(gs)
    gs[name].draw(TransformPen(pen, (k, 0, 0, -k, x, BASE)))
    return f'<path d="{pen.getCommands()}" fill="{fill}"/>', gs[name].width * k
def wordmark(ink, acc):
    parts, x = [], 4.0
    for i, ch in enumerate('slopscope'):
        if i == 6:  # the second "o"
            w = gs[cmap[ord('o')]].width * k
            cx, r = x + w / 2, SIZE * 0.235
            parts.append(f'<circle cx="{cx:.2f}" cy="{BASE - r - 1:.2f}" r="{r:.2f}" fill="none" stroke="{acc}" stroke-width="5.2"/>')
            x += w
            continue
        p, w = glyph(ch, x, ink); parts.append(p); x += w - 0.6
    return ''.join(parts), x + 4

CONCEPTS = {
    'reticle': (reticle, 'Drip reticle'),
    'halflens': (halflens, 'Half lens'),
    'sscope': (sscope, 'S scope'),
    'ruler': (ruler, 'Ruler loupe'),
}
OUT.mkdir(parents=True, exist_ok=True)
for key, (fn, title) in CONCEPTS.items():
    (OUT / f'{key}.svg').write_text(svg('0 0 64 64', fn(INK, ACC), f'slopscope {title}'))
    (OUT / f'{key}-dark.svg').write_text(svg('0 0 64 64', fn(INK_D, ACC_D), f'slopscope {title}'))
for suffix, ink, acc in (('', INK, ACC), ('-dark', INK_D, ACC_D)):
    body, width = wordmark(ink, acc)
    (OUT / f'wordmark{suffix}.svg').write_text(svg(f'0 0 {width:.0f} 60', body, 'slopscope'))
print('ok', width)

# Final assets: mark, wordmark, and a lockup (mark + wordmark) in light and dark.
ASSETS = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
if ASSETS:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for suffix, ink, acc in (('', INK, ACC), ('-dark', INK_D, ACC_D)):
        (ASSETS / f'logo{suffix}.svg').write_text(svg('0 0 64 64', reticle(ink, acc), 'slopscope'))
        body, width = wordmark(ink, acc)
        (ASSETS / f'wordmark{suffix}.svg').write_text(svg(f'0 0 {width:.0f} 60', body, 'slopscope'))
        lock = f'{reticle(ink, acc)}<g transform="translate(70 4)">{body}</g>'
        (ASSETS / f'lockup{suffix}.svg').write_text(svg(f'0 0 {70 + width:.0f} 64', lock, 'slopscope'))

# App icon: the mark in light ink on a dark rounded square, readable on any page color.
if ASSETS:
    icon = ('<rect x="0.75" y="0.75" width="62.5" height="62.5" rx="13.5" fill="#18181B" stroke="#52525B" stroke-width="1.5"/>'
            f'<g transform="translate(9 9) scale(0.72)">{reticle(INK_D, ACC)}</g>')
    (ASSETS / 'app-icon.svg').write_text(svg('0 0 64 64', icon, 'slopscope app icon'))
