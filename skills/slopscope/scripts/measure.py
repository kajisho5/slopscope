"""Measure a web page in Chromium and write measure.json (slopscope checks M-01 to M-09).

    python3 measure.py TARGET [--out measure.json] [--viewports 375,1280] [--themes light,dark]
                              [--click SELECTOR ...] [--wait MS]

TARGET is a URL or a local HTML file. Needs Python 3.11+, Playwright and Pillow
(see requirements.txt). Set CHROMIUM_PATH to use a browser other than
Playwright's own Chromium.

--click dismisses something before measuring (a cookie banner, say); it may be
given more than once. --wait adds a pause after loading for pages that keep
drawing after they load. Dark is measured only when the page responds to it.

Every finding is a measurement, not an opinion. Limits are listed in
references/measurements.md and repeated in the JSON under "not_verified".
"""
import argparse
import collections
import datetime
import io
import json
import pathlib
import sys

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

from slopscope_page import launch, open_page, resolve_themes

TEXT_MIN, LARGE_TEXT_MIN = 4.5, 3.0        # WCAG 1.4.3
RING_MIN, RING_PIXELS = 3.0, 12            # 12 changed pixels = visible (WCAG 2.4.7); at 3:1 = the 2.4.13 (AAA) test
TARGET_MIN = 24                            # WCAG 2.5.8 (AA)
INPUT_MIN_PX = 16                          # iOS Safari zooms on focus below 16px
MAX_TEXT, MAX_STOPS = 300, 60
UNEVEN_BACKGROUND = 0.4                    # below this share of one color, the background is an image or gradient
INTERACTIVE_ROLES = {'button', 'link', 'textbox', 'searchbox', 'combobox', 'checkbox', 'radio', 'switch',
                     'slider', 'spinbutton', 'menuitem', 'tab', 'listbox', 'option'}
NOT_VERIFIED = ['screen readers', 'Safari and Firefox', 'real devices', '200% zoom',
                'states not reachable from the first render (menus, dialogs, hover-only content)',
                'content inside iframes', 'closed shadow roots']


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
    Anti-aliasing only lowers what a pixel shows, so small text can read lower than its CSS colors.
    Returns (ratio, background, text, share of the background color)."""
    image = Image.open(io.BytesIO(png)).convert('RGB')
    colors = image.getcolors(image.width * image.height)  # [(count, rgb)], one entry per distinct color
    total = sum(n for n, _ in colors)
    share, bg = max(colors)
    fg = max((c for _, c in colors), key=lambda c: ratio(c, bg))
    return round(ratio(fg, bg), 2), '#%02x%02x%02x' % bg, '#%02x%02x%02x' % fg, share / total


def ring_pixels(focused_png, blurred_png):
    """Compare a stop focused and blurred. Returns (changed, strong): pixels that differ at all,
    and pixels that differ by 3:1 or more (the WCAG 2.4.13 AAA test). Both stop at RING_PIXELS."""
    a = Image.open(io.BytesIO(focused_png)).convert('RGB')
    b = Image.open(io.BytesIO(blurred_png)).convert('RGB')
    if a.size != b.size:
        return 0, 0
    box = ImageChops.difference(a, b).getbbox()
    if not box:
        return 0, 0
    changed = strong = 0
    for p, q in zip(_pixels(a.crop(box)), _pixels(b.crop(box))):
        if p != q:
            changed += 1
            if strong < RING_PIXELS and ratio(p, q) >= RING_MIN:
                strong += 1
                if strong >= RING_PIXELS:
                    break
    return min(changed, RING_PIXELS), strong


# ---------- page scripts -----------------------------------------------------
# Each script starts with HELPERS_JS. They walk into open shadow roots, so web
# components are measured too, and build a selector that is unique in its page.

HELPERS_JS = r'''
const up=(e)=>e.parentElement||((e.getRootNode&&e.getRootNode().host)||null);
const deep=(root)=>{const out=[];const walk=r=>{for(const e of r.querySelectorAll('*')){out.push(e);if(e.shadowRoot)walk(e.shadowRoot)}};walk(root);return out};
const shown=(e)=>!e.checkVisibility||e.checkVisibility({opacityProperty:true,visibilityProperty:true});
const pageSize=()=>{const de=document.documentElement;return [Math.max(de.scrollWidth,de.clientWidth),Math.max(de.scrollHeight,document.body?document.body.scrollHeight:0)]};
const sel=(el)=>{
  const hashed=/^(css|sc|jsx|emotion|svelte|styled)-|[0-9a-f]{6,}|^_|__[a-zA-Z0-9]{5}$/;
  const path=(el)=>{
    const root=el.getRootNode(), parts=[];
    for(let e=el;e&&e.nodeType===1;e=e.parentElement){
      let s=e.tagName.toLowerCase();
      if(e.id&&!hashed.test(e.id))s+='#'+CSS.escape(e.id);
      else{
        s+=[...e.classList].filter(c=>c.length<=30&&!hashed.test(c)).slice(0,2).map(c=>'.'+CSS.escape(c)).join('');
        const same=e.parentElement?[...e.parentElement.children].filter(c=>c.tagName===e.tagName):[];
        if(same.length>1)s+=':nth-of-type('+(same.indexOf(e)+1)+')';
      }
      parts.unshift(s);
      try{if((parts.length>=2||e.id)&&root.querySelectorAll(parts.join(' > ')).length===1)break}catch(_){}
    }
    return parts.join(' > ');
  };
  const parts=[];
  for(let e=el;e;){parts.unshift(path(e));const r=e.getRootNode();e=r&&r.host?r.host:null}
  return parts.join(' >>> ');
};
'''


def js(body):
    """Put HELPERS_JS at the top of an arrow function given as text."""
    params, _, code = body.partition('=>')
    return params.strip() + '=>{' + HELPERS_JS + code.strip()[1:]


SELECTOR_JS = js('(el)=>{return sel(el)}')
ACTIVE_JS = '()=>{let a=document.activeElement;while(a&&a.shadowRoot&&a.shadowRoot.activeElement)a=a.shadowRoot.activeElement;return a}'
SEEN_JS = '(e)=>{const s=window.__slopscopeSeen||(window.__slopscopeSeen=[]);const i=s.indexOf(e);if(i<0)s.push(e);return i}'

# The visible part of a text node: inside the page and inside every box that clips it,
# the element's own included. Text placed off the page, slides outside a carousel and
# "visually hidden" screen-reader text have no contrast to measure (null).
VISIBLE_BOX_JS = r'''
const vbox=(el,t)=>{
  const de=document.documentElement, [dw,dh]=pageSize();
  const range=document.createRange(); range.selectNodeContents(t);
  const r=range.getBoundingClientRect();
  if(r.width<2||r.height<2)return null;
  let L=r.left, T=r.top, R=r.right, B=r.bottom;
  for(let a=el;a&&a!==document.body&&a!==de;a=up(a)){
    const s=getComputedStyle(a);
    if(s.overflowX==='visible'&&s.overflowY==='visible'&&s.clip==='auto'&&s.clipPath==='none')continue;
    const c=a.getBoundingClientRect();
    L=Math.max(L,c.left); T=Math.max(T,c.top); R=Math.min(R,c.right); B=Math.min(B,c.bottom);
    if(s.clip!=='auto'&&/rect\(0(px)?,? 0(px)?,? 0(px)?,? 0(px)?\)/.test(s.clip))R=L;
    if(/inset\(50%/.test(s.clipPath))R=L;
  }
  const x0=Math.max(0,L+scrollX), y0=Math.max(0,T+scrollY), x1=Math.min(dw,R+scrollX), y1=Math.min(dh,B+scrollY);
  return x1-x0<2||y1-y0<2?null:[x0,y0,x1-x0,y1-y0];
};
'''

TEXT_NODES_JS = js(r'''(max)=>{''' + VISIBLE_BOX_JS + r'''
  const out=[], keep=window.__slopscopeText=[];
  for(const el of [document.body,...deep(document.body)]){
    if(out.length>=max)break;
    const t=[...el.childNodes].find(n=>n.nodeType===3&&n.textContent.trim()); if(!t)continue;
    if(el.closest('script,style,noscript,template,svg,[aria-hidden="true"],[inert]')||!shown(el))continue;
    if(!vbox(el,t))continue;
    const cs=getComputedStyle(el), size=parseFloat(cs.fontSize), weight=parseInt(cs.fontWeight)||400;
    keep.push([el,t]);
    out.push({index:keep.length-1,selector:sel(el),text:t.textContent.trim().slice(0,40),
      large:size>=24||(size>=18.66&&weight>=700),disabled:!!el.closest(':disabled,[aria-disabled="true"]')});
  }
  return out;
}''')

# Where text item i is now: asked again right before its screenshot, in case the page moved.
TEXT_BOX_JS = js(r'''(i)=>{''' + VISIBLE_BOX_JS + r'''
  const [el,t]=window.__slopscopeText[i]; return el.isConnected?vbox(el,t):null;
}''')

GEOMETRY_JS = js(r'''(el)=>{
  const cs=getComputedStyle(el), r=el.getBoundingClientRect(), de=document.documentElement;
  const outline=cs.outlineStyle!=='none'&&parseFloat(cs.outlineWidth)>0?Math.max(0,parseFloat(cs.outlineWidth)+(parseFloat(cs.outlineOffset)||0)):0;
  let shadow=0;
  if(cs.boxShadow&&cs.boxShadow!=='none')for(const part of cs.boxShadow.split(/,(?![^(]*\))/)){
    if(/inset/.test(part))continue;
    const n=(part.replace(/[a-z]+\([^)]*\)/g,'').match(/-?[\d.]+px/g)||[]).map(parseFloat);
    const [x=0,y=0,blur=0,spread=0]=n; shadow=Math.max(shadow,spread+blur/2+Math.max(Math.abs(x),Math.abs(y)));
  }
  const extent=Math.max(outline,shadow); let clippedBy=null;
  if(extent>0){
    const want={l:r.left-extent,t:r.top-extent,r:r.right+extent,b:r.bottom+extent};
    for(let a=up(el);a&&a!==document.body&&a!==de;a=up(a)){
      const s=getComputedStyle(a);
      if(s.overflowX==='visible'&&s.overflowY==='visible'&&s.clipPath==='none')continue;
      const c=a.getBoundingClientRect();
      if(Math.max(c.left-want.l,c.top-want.t,want.r-c.right,want.b-c.bottom)>0.5){clippedBy=sel(a);break}
    }
  }
  const textField=el.isContentEditable||el.tagName==='TEXTAREA'||(el.tagName==='INPUT'&&!['checkbox','radio','range','color','file','button','submit','reset','image'].includes(el.type));
  return {box:[r.left+scrollX,r.top+scrollY,r.width,r.height],extent,clippedBy,textField,
          frame:el.tagName==='IFRAME',page:pageSize()};
}''')

OVERFLOW_JS = js(r'''()=>{
  const de=document.documentElement, w=de.clientWidth, out=[];
  // Ask the browser whether the page really scrolls sideways. overflow-x:hidden or clip on
  // html/body (often used to hide off-canvas menus) means it does not.
  const x0=scrollX; scrollTo(1e6,scrollY); const moved=scrollX; scrollTo(x0,scrollY);
  const bs=getComputedStyle(document.body);
  const bodyScrolls=['auto','scroll'].includes(bs.overflowX)&&document.body.scrollWidth>document.body.clientWidth+1;
  const scrolls=moved>0||bodyScrolls;
  if(scrolls)for(const el of deep(document.body)){
    const r=el.getBoundingClientRect();
    if(r.width===0||r.right<=w+0.5)continue;
    if(el.closest('[aria-hidden="true"]')||getComputedStyle(el).position==='fixed')continue;
    const p=up(el);
    if(p&&p!==document.body&&p.getBoundingClientRect().right>w+0.5)continue;  // outermost only
    let inScroller=false;
    for(let a=p;a&&a!==document.body&&a!==de;a=up(a)){if(getComputedStyle(a).overflowX!=='visible'){inScroller=true;break}}
    if(!inScroller)out.push({selector:sel(el),overflow_px:Math.round(r.right-w)});
  }
  return {page_scrolls:scrolls,scroll_px:Math.round(Math.max(moved,de.scrollWidth-w)),elements:out.slice(0,20)};
}''')

INPUTS_JS = js(r'''()=>{
  const skip=new Set(['checkbox','radio','range','color','file','button','submit','reset','image','hidden']);
  return deep(document.body).filter(e=>/^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName)&&!skip.has(e.type)&&e.getClientRects().length&&shown(e))
    .map(e=>({selector:sel(e),font_px:parseFloat(getComputedStyle(e).fontSize)}));
}''')

TARGETS_JS = js(r'''()=>{
  const q='a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button],[role=link],[role=checkbox],[role=radio],[role=switch],[role=tab],[role=menuitem],[tabindex]:not([tabindex="-1"])';
  const [dw]=pageSize(), all=[];
  for(const e of deep(document.body)){
    if(!e.matches(q)||e.closest('[inert]')||!shown(e))continue;
    let r=e.getBoundingClientRect(); if(!r.width||!r.height)continue;
    if(r.right+scrollX<=0||r.left+scrollX>=dw)continue;  // off the page: nobody can tap it
    // WCAG 2.5.8 inline exception: links inside a sentence
    // (an inline link whose nearest block holds other text, however deep the spans go)
    if(e.tagName==='A'&&getComputedStyle(e).display==='inline'){
      let b=e.parentElement; while(b&&getComputedStyle(b).display.startsWith('inline'))b=b.parentElement;
      // count only words that are not links, so a row of links is not a sentence
      const words=b?[...b.querySelectorAll('a,button')].reduce((n,l)=>n-l.textContent.replace(/\s+/g,'').length,b.textContent.replace(/\s+/g,'').length):0;
      if(words>=10)continue;
    }
    // A label activates its control, so the label is part of the target.
    if(e.labels&&e.labels.length){
      let L=r.left,T=r.top,R=r.right,B=r.bottom;
      for(const l of e.labels){const b=l.getBoundingClientRect();if(!b.width)continue;L=Math.min(L,b.left);T=Math.min(T,b.top);R=Math.max(R,b.right);B=Math.max(B,b.bottom)}
      r={left:L,top:T,right:R,bottom:B,width:R-L,height:B-T};
    }
    // A link that wraps onto two lines is two boxes; the box around both covers its neighbours.
    const parts=e.labels&&e.labels.length?[r]:[...e.getClientRects()].filter(b=>b.width&&b.height);
    all.push({e,r,parts:parts.length?parts:[r],small:r.width<24||r.height<24,cx:r.left+r.width/2,cy:r.top+r.height/2});
  }
  // WCAG 2.5.8 spacing exception: a 24px circle centred on an undersized target
  // must not intersect another target or another undersized target's circle.
  const toRect=(x,y,r)=>Math.hypot(Math.max(r.left-x,0,x-r.right),Math.max(r.top-y,0,y-r.bottom));
  const inLabel=(a,b)=>a.e.labels&&[...a.e.labels].some(l=>l.contains(b.e));
  const out=[];
  for(const a of all){
    if(!a.small)continue;
    const crowded=all.some(b=>b!==a&&!b.e.contains(a.e)&&!a.e.contains(b.e)&&!inLabel(a,b)&&(b.small?Math.hypot(a.cx-b.cx,a.cy-b.cy)<24:Math.min(...b.parts.map(x=>toRect(a.cx,a.cy,x)))<12));
    if(crowded)out.push({selector:sel(a.e),size:[Math.round(a.r.width),Math.round(a.r.height)]});
  }
  return out;
}''')

ANIMATIONS_JS = js(r'''()=>{
  const out=document.getAnimations().filter(a=>a.playState==='running'&&a.effect&&a.effect.getComputedTiming().iterations===Infinity)
    .map(a=>({selector:a.effect.target?sel(a.effect.target):'(unknown)',name:a.animationName||a.transitionProperty||a.id||'animation'}));
  // Autoplaying video keeps moving too (WCAG 2.2.2 asks for a way to pause it).
  for(const v of deep(document.body))if(v.tagName==='VIDEO'&&!v.paused&&(v.loop||v.duration>5))
    out.push({selector:sel(v),name:'autoplaying video',controls:v.controls});
  return out.slice(0,20);
}''')

VARIETY_JS = js(r'''()=>{
  const count=(m,k)=>m.set(k,(m.get(k)||0)+1);
  const color=new Map(),bg=new Map(),font=new Map(),space=new Map();
  for(const e of deep(document.body)){
    if(!e.getClientRects().length)continue;
    const s=getComputedStyle(e);
    if([...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())){count(color,s.color);count(font,s.fontSize)}
    if(s.backgroundColor!=='rgba(0, 0, 0, 0)')count(bg,s.backgroundColor);
    for(const p of ['marginTop','marginBottom','paddingTop','paddingLeft','rowGap','columnGap']){const v=s[p];if(v&&v!=='0px'&&v!=='normal'&&v!=='auto')count(space,v)}
  }
  const top=m=>[...m.entries()].sort((a,b)=>b[1]-a[1]).slice(0,10).map(([value,uses])=>({value,uses}));
  return {text_colors:{distinct:color.size,top:top(color)},backgrounds:{distinct:bg.size,top:top(bg)},
          font_sizes:{distinct:font.size,top:top(font)},spacing:{distinct:space.size,top:top(space)}};
}''')


# ---------- checks -----------------------------------------------------------

def _shot(page, clip):
    """Screenshot a clip of the full page, or None when the clip falls outside it."""
    try:
        return page.screenshot(clip=clip, full_page=True)
    except Exception:
        return None


def check_contrast(page, viewport, theme):
    findings = []
    for item in page.evaluate(TEXT_NODES_JS, MAX_TEXT):
        if item['disabled']:
            continue
        box = page.evaluate(TEXT_BOX_JS, item['index'])
        if box is None:
            continue
        x, y, w, h = box
        png = _shot(page, {'x': x, 'y': y, 'width': w, 'height': h})
        if png is None:
            continue
        value, bg, fg, share = text_contrast(png)
        need = LARGE_TEXT_MIN if item['large'] else TEXT_MIN
        if value < need:
            finding = {'selector': item['selector'], 'text': item['text'], 'viewport': viewport, 'theme': theme,
                       'value': f'{value}:1', 'needs': f'{need}:1', 'colors': [fg, bg]}
            if share < UNEVEN_BACKGROUND:
                finding['uneven_background'] = True  # image or gradient behind: check by eye
            findings.append(finding)
    return findings


def check_focus(page, viewport, theme, crops_dir=None):
    """Tab through the page; compare each stop focused and blurred.

    fail  : nothing visible changes on focus (WCAG 2.4.7 Focus Visible, AA).
    weak  : something changes, but no 12 pixels change by 3:1 (the 2.4.13 AAA test). Not a
            failure: a fill or color change can be plainly visible at a lower ratio, so the
            crops are saved for a look by eye.
    """
    invisible, clipped, caret_only, weak = [], [], [], []
    page.evaluate('document.activeElement && document.activeElement.blur && document.activeElement.blur()')
    page.evaluate('window.__slopscopeSeen=[]')
    stops = repeats = 0
    for _ in range(MAX_STOPS * 2):
        if stops >= MAX_STOPS:
            break
        page.keyboard.press('Tab')
        handle = page.evaluate_handle(ACTIVE_JS)
        if page.evaluate('(e)=>!e||e===document.body||e===document.documentElement', handle):
            break
        index = page.evaluate(SEEN_JS, handle)
        geo = page.evaluate(GEOMETRY_JS, handle)
        if index == 0 and not geo['frame']:
            break  # focus came back to the first stop: the whole page has been visited
        if index > 0:
            # an iframe holds focus while Tab moves inside it; anything else repeating is a loop
            repeats += 0 if geo['frame'] else 1
            if repeats > 5:
                break
            continue
        stops += 1
        selector = page.evaluate(SELECTOR_JS, handle)
        x, y, w, h = geo['box']
        pw, ph = geo['page']
        pad = 8
        left, top = max(0, x - pad), max(0, y - pad)
        right, bottom = min(pw, x + w + pad), min(ph, y + h + pad)
        where = {'selector': selector, 'viewport': viewport, 'theme': theme}
        if right - left < 2 or bottom - top < 2:
            invisible.append(dict(where, pixels_changed=0, note='focused element is outside the page'))
            continue
        clip = {'x': left, 'y': top, 'width': right - left, 'height': bottom - top}
        focused = _shot(page, clip)
        page.evaluate('(e)=>e.blur()', handle)
        blurred = _shot(page, clip)
        page.evaluate('(e)=>e.focus({preventScroll:true})', handle)
        changed, strong = ring_pixels(focused, blurred) if focused and blurred else (0, 0)
        finding = dict(where, pixels_changed=changed, pixels_at_3to1=strong)
        if strong < RING_PIXELS and crops_dir and focused and blurred:
            crops_dir.mkdir(parents=True, exist_ok=True)
            stem = f'{viewport}-{theme}-stop{stops:02d}'
            (crops_dir / f'{stem}-focused.png').write_bytes(focused)
            (crops_dir / f'{stem}-blurred.png').write_bytes(blurred)
            finding['crops'] = [f'{crops_dir.name}/{stem}-focused.png', f'{crops_dir.name}/{stem}-blurred.png']
        if changed < RING_PIXELS:
            # WCAG 2.4.7's own example: the text cursor in a field is a focus indicator.
            (caret_only if geo['textField'] else invisible).append(finding)
        elif strong < RING_PIXELS:
            weak.append(finding)
        if geo['clippedBy']:
            clipped.append(dict(where, clipped_by=geo['clippedBy']))
    return invisible, clipped, caret_only, weak, stops


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


def color_pairs(findings):
    """Failing text grouped by its colors: one shared color is usually behind many findings."""
    pairs = collections.Counter((f['colors'][0], f['colors'][1]) for f in findings)
    return [{'text': t, 'background': b, 'findings': n} for (t, b), n in pairs.most_common(10)]


def result(check_id, findings, threshold, status=None, **extra):
    return dict({'id': check_id, 'status': status or ('fail' if findings else 'pass'), 'threshold': threshold,
                 'findings': findings}, **extra)


def measure(target, viewports=(375, 1280), themes=('light', 'dark'), clicks=(), wait_ms=0, crops_dir=None):
    found = collections.defaultdict(list)
    stops = 0
    variety = None
    pages = []
    load = {'clicks': clicks, 'wait_ms': wait_ms}
    with sync_playwright() as p:
        browser = launch(p)
        version = browser.version
        themes, dark = resolve_themes(browser, target, min(viewports), themes, **load)
        for viewport in viewports:
            for theme in themes:
                page, info = open_page(browser, target, viewport, theme, scale=2, **load)
                pages.append(dict(info, viewport=viewport, theme=theme))
                found['M-01'] += check_contrast(page, viewport, theme)
                invisible, clipped, caret_only, weak, count = check_focus(page, viewport, theme, crops_dir)
                found['M-02'] += invisible; found['M-03'] += clipped
                found['caret'] += caret_only; found['weak'] += weak
                stops = max(stops, count)
                if theme == themes[0]:
                    found['M-06'] += check_names(page, viewport)
                    found['M-07'] += [dict(f, viewport=viewport) for f in page.evaluate(TARGETS_JS)]
                    if viewport == min(viewports):
                        over = page.evaluate(OVERFLOW_JS)
                        if over['page_scrolls']:
                            found['M-04'] += [dict(e, viewport=viewport) for e in over['elements']] or \
                                [{'selector': 'html', 'viewport': viewport, 'overflow_px': over['scroll_px']}]
                        found['M-05'] += [dict(i, viewport=viewport) for i in page.evaluate(INPUTS_JS) if i['font_px'] < INPUT_MIN_PX]
                    if variety is None:
                        variety = page.evaluate(VARIETY_JS)
                page.close()
        page, info = open_page(browser, target, max(viewports), themes[0], reduced_motion='reduce', freeze=False, **load)
        found['M-08'] = page.evaluate(ANIMATIONS_JS)
        page.close()
        browser.close()
    # M-06/M-07 run once per viewport; drop repeats of the same element.
    for key in ('M-06', 'M-07', 'caret', 'weak'):
        unique = {}
        for f in found[key]:
            unique.setdefault(f['selector'], f)
        found[key] = list(unique.values())
    first = pages[0]
    return {
        'tool': 'slopscope measure.py',
        'target': target,
        'measured_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
        'browser': f'Chromium {version}',
        'page': {'status': first['status'], 'final_url': first['final_url'], 'title': first['title']},
        'warnings': sorted({w for pg in pages for w in pg['warnings']}),
        'clicked': list(clicks),
        'viewports': list(viewports),
        'themes': list(themes),
        'dark_supported': dark,
        'focus_stops': stops,
        'focus_stops_limit_reached': stops >= MAX_STOPS,
        'checks': [
            result('M-01', found['M-01'], '4.5:1 (3:1 for large text)', by_colors=color_pairs(found['M-01'])),
            result('M-02', found['M-02'], f'something visible changes on focus ({RING_PIXELS}+ pixels; WCAG 2.4.7)',
                   weak=found['weak'], caret_only=found['caret']),
            result('M-03', found['M-03'], 'focus indicator not cut by an ancestor'),
            result('M-04', found['M-04'], 'no sideways scroll at the narrowest viewport'),
            result('M-05', found['M-05'], f'text inputs at {INPUT_MIN_PX}px or more at the narrowest viewport'),
            result('M-06', found['M-06'], 'every interactive element has an accessible name'),
            result('M-07', found['M-07'], f'{TARGET_MIN}x{TARGET_MIN}px, or spaced so a {TARGET_MIN}px circle touches no other target (links in sentences exempt)'),
            result('M-08', found['M-08'], 'no infinite animation or autoplaying video with prefers-reduced-motion: reduce'),
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
    parser.add_argument('--click', action='append', default=[], metavar='SELECTOR',
                        help='click this before measuring (e.g. a cookie banner button); repeatable')
    parser.add_argument('--wait', type=int, default=0, metavar='MS', help='extra wait after loading')
    args = parser.parse_args(argv)
    out = pathlib.Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    data = measure(args.target, tuple(int(v) for v in args.viewports.split(',')), tuple(args.themes.split(',')),
                   tuple(args.click), args.wait, crops_dir=out.parent / 'focus')
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')
    for warning in data['warnings']:
        print('warning:', warning)
    if data['dark_supported'] is False:
        print('note: the page ignores prefers-color-scheme: dark, so only light was measured')
    failed = [c['id'] for c in data['checks'] if c['status'] == 'fail']
    for c in data['checks']:
        print(f"{c['id']} {c['status']:<4} {len(c['findings'])} finding(s)")
    print(f'wrote {out}; failed: {", ".join(failed) or "none"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
