"""Measure a web page in Chromium and write measure.json (slopscope checks M-01 to M-09).

    python3 measure.py TARGET [--out measure.json] [--viewports 375,1280] [--themes light,dark]

TARGET is a URL or a local HTML file. Needs Python 3.11+, Playwright and Pillow
(see requirements.txt). Set CHROMIUM_PATH to use a browser other than
Playwright's own Chromium.

Every finding is a measurement, not an opinion. Limits are listed in
references/measurements.md and repeated in the JSON under "not_verified".
"""
import argparse
import collections
import datetime
import io
import json
import os
import pathlib
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

TEXT_MIN, LARGE_TEXT_MIN = 4.5, 3.0        # WCAG 1.4.3
RING_MIN, RING_PIXELS = 3.0, 12            # WCAG 1.4.11 / 2.4.7: 12 changed pixels at 3:1
TARGET_MIN = 24                            # WCAG 2.5.8 (AA)
INPUT_MIN_PX = 16                          # iOS Safari zooms on focus below 16px
MAX_TEXT, MAX_STOPS = 300, 40
INTERACTIVE_ROLES = {'button', 'link', 'textbox', 'searchbox', 'combobox', 'checkbox', 'radio', 'switch',
                     'slider', 'spinbutton', 'menuitem', 'tab', 'listbox', 'option'}
NOT_VERIFIED = ['screen readers', 'Safari and Firefox', 'real devices', '200% zoom',
                'states not reachable from the first render (menus, dialogs, hover-only content)']


# ---------- pixels -----------------------------------------------------------

def _lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def ratio(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _pixels(image):
    return list(image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata())


def text_contrast(png):
    """Background = most common pixel; text = the pixel with the highest contrast against it.
    Anti-aliasing only lowers what a pixel shows, so small text can read lower than its CSS colors."""
    image = Image.open(io.BytesIO(png)).convert('RGB')
    pixels = _pixels(image)
    bg = collections.Counter(pixels).most_common(1)[0][0]
    fg = max(pixels, key=lambda p: ratio(p, bg))
    return round(ratio(fg, bg), 2), '#%02x%02x%02x' % bg, '#%02x%02x%02x' % fg


def ring_pixels(focused_png, blurred_png):
    a = Image.open(io.BytesIO(focused_png)).convert('RGB')
    b = Image.open(io.BytesIO(blurred_png)).convert('RGB')
    if a.size != b.size:
        return 0
    return sum(1 for p, q in zip(_pixels(a), _pixels(b)) if p != q and ratio(p, q) >= RING_MIN)


# ---------- page scripts -----------------------------------------------------

SELECTOR_JS = r'''(el)=>{
  const parts=[];
  for(let e=el;e&&e.nodeType===1&&parts.length<4;e=e.parentElement){
    let s=e.tagName.toLowerCase();
    if(e.id){s+='#'+CSS.escape(e.id);parts.unshift(s);break}
    const cls=[...e.classList].slice(0,2).map(c=>'.'+CSS.escape(c)).join('');
    s+=cls;
    const same=e.parentElement?[...e.parentElement.children].filter(c=>c.tagName===e.tagName):[];
    if(same.length>1)s+=':nth-of-type('+(same.indexOf(e)+1)+')';
    parts.unshift(s);
  }
  return parts.join(' > ');
}'''

TEXT_NODES_JS = r'''(max)=>{
  const sel=''' + SELECTOR_JS + r''';
  const out=[];
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  const seen=new Set();
  while(walker.nextNode()&&out.length<max){
    const t=walker.currentNode; if(!t.textContent.trim())continue;
    const el=t.parentElement; if(!el||seen.has(el))continue; seen.add(el);
    if(el.closest('script,style,noscript,svg,[aria-hidden="true"]'))continue;
    const cs=getComputedStyle(el);
    if(cs.visibility!=='visible'||+cs.opacity===0)continue;
    const range=document.createRange(); range.selectNodeContents(t);
    const r=range.getBoundingClientRect();
    if(r.width<2||r.height<2)continue;
    const size=parseFloat(cs.fontSize), weight=parseInt(cs.fontWeight)||400;
    const disabled=!!el.closest(':disabled,[aria-disabled="true"]');
    out.push({selector:sel(el),text:t.textContent.trim().slice(0,40),box:[r.left+scrollX,r.top+scrollY,r.width,r.height],
      large:size>=24||(size>=18.66&&weight>=700),disabled});
  }
  return out;
}'''

GEOMETRY_JS = r'''(el)=>{
  const cs=getComputedStyle(el), r=el.getBoundingClientRect();
  const outline=cs.outlineStyle!=='none'&&parseFloat(cs.outlineWidth)>0?Math.max(0,parseFloat(cs.outlineWidth)+(parseFloat(cs.outlineOffset)||0)):0;
  let shadow=0;
  if(cs.boxShadow&&cs.boxShadow!=='none')for(const part of cs.boxShadow.split(/,(?![^(]*\))/)){
    if(/inset/.test(part))continue;
    const n=(part.replace(/rgba?\([^)]*\)|oklch\([^)]*\)|color\([^)]*\)/g,'').match(/-?[\d.]+px/g)||[]).map(parseFloat);
    const [x=0,y=0,blur=0,spread=0]=n; shadow=Math.max(shadow,spread+blur/2+Math.max(Math.abs(x),Math.abs(y)));
  }
  const extent=Math.max(outline,shadow); let clippedBy=null;
  if(extent>0){
    const want={l:r.left-extent,t:r.top-extent,r:r.right+extent,b:r.bottom+extent};
    for(let a=el.parentElement;a&&a!==document.body;a=a.parentElement){
      const s=getComputedStyle(a);
      if(s.overflowX==='visible'&&s.overflowY==='visible'&&s.clipPath==='none')continue;
      const c=a.getBoundingClientRect();
      if(Math.max(c.left-want.l,c.top-want.t,want.r-c.right,want.b-c.bottom)>0.5){clippedBy=a.tagName.toLowerCase()+(a.className&&typeof a.className==='string'?'.'+a.className.trim().split(/\s+/)[0]:'');break}
    }
  }
  return {box:[r.left+scrollX,r.top+scrollY,r.width,r.height],extent,clippedBy};
}'''

OVERFLOW_JS = r'''()=>{
  const sel=''' + SELECTOR_JS + r''';
  const w=document.documentElement.clientWidth, out=[];
  for(const el of document.body.querySelectorAll('*')){
    const r=el.getBoundingClientRect();
    if(r.width===0||r.right<=w+0.5)continue;
    if(el.closest('[aria-hidden="true"]'))continue;
    // report the outermost overflowing element only
    if(el.parentElement&&el.parentElement.getBoundingClientRect().right>w+0.5&&el.parentElement!==document.body)continue;
    let a=el.parentElement,scrolls=false;
    for(;a&&a!==document.body;a=a.parentElement){const s=getComputedStyle(a);if(s.overflowX!=='visible'){scrolls=true;break}}
    if(!scrolls)out.push({selector:sel(el),overflow_px:Math.round(r.right-w)});
  }
  return {page_scrolls:document.documentElement.scrollWidth>w,elements:out.slice(0,20)};
}'''

INPUTS_JS = r'''()=>{
  const sel=''' + SELECTOR_JS + r''';
  const skip=new Set(['checkbox','radio','range','color','file','button','submit','reset','image','hidden']);
  return [...document.querySelectorAll('input,textarea,select')].filter(e=>!skip.has(e.type)&&e.getClientRects().length)
    .map(e=>({selector:sel(e),font_px:parseFloat(getComputedStyle(e).fontSize)}));
}'''

TARGETS_JS = r'''()=>{
  const sel=''' + SELECTOR_JS + r''';
  const q='a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button],[role=link],[role=checkbox],[role=switch],[role=tab],[tabindex]:not([tabindex="-1"])';
  const all=[];
  for(const e of document.querySelectorAll(q)){
    const r=e.getBoundingClientRect(); if(!r.width||!r.height)continue;
    // WCAG 2.5.8 inline exception: links inside a sentence
    if(e.tagName==='A'){const p=e.parentElement;if(p&&/^(P|LI|SPAN|TD|DD)$/.test(p.tagName)&&p.textContent.trim().length>e.textContent.trim().length+10)continue}
    all.push({e,r,small:r.width<24||r.height<24,cx:r.left+r.width/2,cy:r.top+r.height/2});
  }
  // WCAG 2.5.8 spacing exception: a 24px circle centred on an undersized target
  // must not intersect another target or another undersized target's circle.
  const toRect=(x,y,r)=>Math.hypot(Math.max(r.left-x,0,x-r.right),Math.max(r.top-y,0,y-r.bottom));
  const out=[];
  for(const a of all){
    if(!a.small)continue;
    const crowded=all.some(b=>b!==a&&!b.e.contains(a.e)&&!a.e.contains(b.e)&&(b.small?Math.hypot(a.cx-b.cx,a.cy-b.cy)<24:toRect(a.cx,a.cy,b.r)<12));
    if(crowded)out.push({selector:sel(a.e),size:[Math.round(a.r.width),Math.round(a.r.height)]});
  }
  return out;
}'''

ANIMATIONS_JS = r'''()=>{
  const sel=''' + SELECTOR_JS + r''';
  return document.getAnimations().filter(a=>a.playState==='running'&&a.effect&&a.effect.getComputedTiming().iterations===Infinity)
    .map(a=>({selector:a.effect.target?sel(a.effect.target):'(unknown)',name:a.animationName||a.transitionProperty||a.id||'animation'})).slice(0,20);
}'''

VARIETY_JS = r'''()=>{
  const count=(m,k)=>m.set(k,(m.get(k)||0)+1);
  const color=new Map(),bg=new Map(),font=new Map(),space=new Map();
  for(const e of document.body.querySelectorAll('*')){
    if(!e.getClientRects().length)continue;
    const s=getComputedStyle(e);
    if(e.childNodes.length&&[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())){count(color,s.color);count(font,s.fontSize)}
    if(s.backgroundColor!=='rgba(0, 0, 0, 0)')count(bg,s.backgroundColor);
    for(const p of ['marginTop','marginBottom','paddingTop','paddingLeft','rowGap','columnGap']){const v=s[p];if(v&&v!=='0px'&&v!=='normal'&&v!=='auto')count(space,v)}
  }
  const top=m=>[...m.entries()].sort((a,b)=>b[1]-a[1]).slice(0,10).map(([value,uses])=>({value,uses}));
  return {text_colors:{distinct:color.size,top:top(color)},backgrounds:{distinct:bg.size,top:top(bg)},
          font_sizes:{distinct:font.size,top:top(font)},spacing:{distinct:space.size,top:top(space)}};
}'''


# ---------- checks -----------------------------------------------------------

def check_contrast(page, viewport, theme):
    findings = []
    for item in page.evaluate(TEXT_NODES_JS, MAX_TEXT):
        if item['disabled']:
            continue
        x, y, w, h = item['box']
        png = page.screenshot(clip={'x': x, 'y': y, 'width': max(w, 1), 'height': max(h, 1)}, full_page=True)
        value, bg, fg = text_contrast(png)
        need = LARGE_TEXT_MIN if item['large'] else TEXT_MIN
        if value < need:
            findings.append({'selector': item['selector'], 'text': item['text'], 'viewport': viewport, 'theme': theme,
                             'value': f'{value}:1', 'needs': f'{need}:1', 'colors': [fg, bg]})
    return findings


def check_focus(page, viewport, theme):
    """Tab through the page; compare each stop focused and blurred."""
    invisible, clipped = [], []
    page.evaluate('document.activeElement && document.activeElement.blur()')
    seen = set()
    for _ in range(MAX_STOPS):
        page.keyboard.press('Tab')
        handle = page.evaluate_handle('document.activeElement')
        if page.evaluate('(e)=>e===document.body||e===null', handle):
            break
        selector = page.evaluate(SELECTOR_JS, handle)
        if selector in seen:
            break
        seen.add(selector)
        geo = page.evaluate(GEOMETRY_JS, handle)
        x, y, w, h = geo['box']
        pad = 8
        clip = {'x': max(0, x - pad), 'y': max(0, y - pad), 'width': w + 2 * pad, 'height': h + 2 * pad}
        if clip['width'] < 2 or clip['height'] < 2:
            continue
        focused = page.screenshot(clip=clip, full_page=True)
        page.evaluate('(e)=>e.blur()', handle)
        blurred = page.screenshot(clip=clip, full_page=True)
        page.evaluate('(e)=>e.focus({preventScroll:true})', handle)
        count = ring_pixels(focused, blurred)
        if count < RING_PIXELS:
            invisible.append({'selector': selector, 'viewport': viewport, 'theme': theme, 'pixels_at_3to1': count})
        if geo['clippedBy']:
            clipped.append({'selector': selector, 'viewport': viewport, 'theme': theme, 'clipped_by': geo['clippedBy']})
    return invisible, clipped, len(seen)


def check_names(page, viewport):
    cdp = page.context.new_cdp_session(page)
    nodes = cdp.send('Accessibility.getFullAXTree')['nodes']
    findings = []
    for node in nodes:
        role = (node.get('role') or {}).get('value')
        if role not in INTERACTIVE_ROLES or node.get('ignored'):
            continue
        name = ((node.get('name') or {}).get('value') or '').strip()
        if name or 'backendDOMNodeId' not in node:
            continue
        try:
            obj = cdp.send('DOM.resolveNode', {'backendNodeId': node['backendDOMNodeId']})['object']
            selector = cdp.send('Runtime.callFunctionOn', {'objectId': obj['objectId'], 'functionDeclaration': 'function(){return (' + SELECTOR_JS + ')(this)}', 'returnByValue': True})['result'].get('value')
        except Exception:  # node gone or not resolvable; still report the role
            selector = '(unresolved)'
        findings.append({'selector': selector, 'role': role, 'viewport': viewport})
    cdp.detach()
    return findings


def result(check_id, findings, threshold, status=None):
    return {'id': check_id, 'status': status or ('fail' if findings else 'pass'), 'threshold': threshold, 'findings': findings}


def load(page, target, freeze=True):
    url = target if '://' in target else pathlib.Path(target).resolve().as_uri()
    page.goto(url, wait_until='load')
    page.wait_for_timeout(300)
    if freeze:
        # Measure every page in its resting state: animations are paused at their start.
        page.evaluate('document.getAnimations().forEach(a=>{a.pause();a.currentTime=0})')


def measure(target, viewports=(375, 1280), themes=('light', 'dark')):
    found = collections.defaultdict(list)
    stops = 0
    variety = None
    with sync_playwright() as p:
        launch = {'args': ['--no-sandbox']}
        if os.environ.get('CHROMIUM_PATH'):
            launch['executable_path'] = os.environ['CHROMIUM_PATH']
        browser = p.chromium.launch(**launch)
        version = browser.version
        for viewport in viewports:
            for theme in themes:
                page = browser.new_page(viewport={'width': viewport, 'height': 900}, color_scheme=theme, device_scale_factor=2)
                load(page, target)
                found['M-01'] += check_contrast(page, viewport, theme)
                invisible, clipped, count = check_focus(page, viewport, theme)
                found['M-02'] += invisible; found['M-03'] += clipped; stops = max(stops, count)
                if theme == themes[0]:
                    found['M-06'] += check_names(page, viewport)
                    found['M-07'] += [dict(f, viewport=viewport) for f in page.evaluate(TARGETS_JS)]
                    if viewport == min(viewports):
                        over = page.evaluate(OVERFLOW_JS)
                        if over['page_scrolls'] or over['elements']:
                            found['M-04'] += [dict(e, viewport=viewport) for e in over['elements']] or [{'selector': 'html', 'viewport': viewport, 'overflow_px': None}]
                        found['M-05'] += [dict(i, viewport=viewport) for i in page.evaluate(INPUTS_JS) if i['font_px'] < INPUT_MIN_PX]
                    if variety is None:
                        variety = page.evaluate(VARIETY_JS)
                page.close()
        page = browser.new_page(viewport={'width': max(viewports), 'height': 900}, reduced_motion='reduce')
        load(page, target, freeze=False)
        found['M-08'] = page.evaluate(ANIMATIONS_JS)
        page.close()
        browser.close()
    # M-06/M-07 run once per viewport; drop repeats of the same element.
    for key in ('M-06', 'M-07'):
        unique = {}
        for f in found[key]:
            unique.setdefault(f['selector'], f)
        found[key] = list(unique.values())
    return {
        'tool': 'slopscope measure.py',
        'target': target,
        'measured_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
        'browser': f'Chromium {version}',
        'viewports': list(viewports),
        'themes': list(themes),
        'focus_stops': stops,
        'checks': [
            result('M-01', found['M-01'], '4.5:1 (3:1 for large text)'),
            result('M-02', found['M-02'], f'{RING_PIXELS}+ pixels change at {RING_MIN}:1 on focus'),
            result('M-03', found['M-03'], 'focus indicator not cut by an ancestor'),
            result('M-04', found['M-04'], 'no sideways scroll at the narrowest viewport'),
            result('M-05', found['M-05'], f'text inputs at {INPUT_MIN_PX}px or more at the narrowest viewport'),
            result('M-06', found['M-06'], 'every interactive element has an accessible name'),
            result('M-07', found['M-07'], f'{TARGET_MIN}x{TARGET_MIN}px, or spaced so a {TARGET_MIN}px circle touches no other target (links in sentences exempt)'),
            result('M-08', found['M-08'], 'no infinite animation with prefers-reduced-motion: reduce'),
            {'id': 'M-09', 'status': 'info', 'threshold': 'none (reference)', 'findings': [], 'variety': variety},
        ],
        'not_verified': NOT_VERIFIED,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('target')
    parser.add_argument('--out', default='slopscope-report/measure.json')
    parser.add_argument('--viewports', default='375,1280')
    parser.add_argument('--themes', default='light,dark')
    args = parser.parse_args(argv)
    data = measure(args.target, tuple(int(v) for v in args.viewports.split(',')), tuple(args.themes.split(',')))
    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')
    failed = [c['id'] for c in data['checks'] if c['status'] == 'fail']
    for c in data['checks']:
        print(f"{c['id']} {c['status']:<4} {len(c['findings'])} finding(s)")
    print(f'wrote {out}; failed: {", ".join(failed) or "none"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
