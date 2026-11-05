"""Shared page loading for snapshot.py and measure.py.

Real sites are not test pages: they load content late, hide it until scrolled to,
block headless browsers, and cover the page with cookie banners. Every script opens
pages through open_page() so both see the same settled page.
"""
import os
import pathlib
import re


GOTO_TIMEOUT_MS = 45_000
IDLE_TIMEOUT_MS = 5_000
SCROLL_STEPS = 40
# Titles that bot checks and error pages use. A match is a warning, not a verdict.
BLOCKED_TITLE = re.compile(r'just a moment|attention required|access denied|forbidden|captcha|'
                           r'verify (you are|that you are) (a )?human|are you a robot|security check|'
                           r'page not found|\b40[34]\b', re.I)

# Measurement aids, not changes to the design: transitions end at once so a screenshot
# shows the final state, the blinking text cursor is hidden so two shots match, smooth
# scrolling is off so scrolled positions are exact, and content-visibility:auto parts are
# drawn (Chromium leaves them blank in a full-page screenshot when they are off screen).
SETTLE_CSS = ('*,*::before,*::after{transition-duration:0s!important;transition-delay:0s!important;'
              'caret-color:transparent!important;scroll-behavior:auto!important;'
              'content-visibility:visible!important}')

# Animations that end (fade-ins, slide-ins) are jumped to their end, so content is measured
# as it rests; endless ones are paused at their start. Either way two runs match.
# Timers the page already set are cleared too: carousels that rotate on a timer would
# otherwise move content while it is being measured.
FREEZE_JS = r'''()=>{
  document.getAnimations().forEach(a=>{try{
    const t=a.effect&&a.effect.getComputedTiming();
    if(t&&t.endTime!==Infinity)a.finish(); else {a.pause();a.currentTime=0}
  }catch(e){}});
  const last=setTimeout(()=>{},0);
  for(let i=0;i<=last;i++){clearTimeout(i);clearInterval(i)}
}'''

# Resolves once the page has not changed for `quiet` ms (or after `limit` ms), so pages
# that draw themselves with JavaScript after loading are measured once drawn.
QUIET_JS = r'''async ([quiet,limit])=>{await new Promise(done=>{
  let t; const end=()=>{obs.disconnect();done()};
  const obs=new MutationObserver(()=>{clearTimeout(t);t=setTimeout(end,quiet)});
  obs.observe(document,{subtree:true,childList:true,attributes:true,characterData:true});
  t=setTimeout(end,quiet); setTimeout(end,limit);
})}'''

SCROLL_JS = r'''async (steps)=>{
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  const h=innerHeight;
  for(let i=0,y=0;i<steps;i++){
    y+=h; scrollTo(0,y); await sleep(120);
    if(y>=document.documentElement.scrollHeight)break;
  }
  scrollTo(0,0); await sleep(200);
}'''


def launch(playwright):
    options = {'args': ['--no-sandbox']}
    if os.environ.get('CHROMIUM_PATH'):
        options['executable_path'] = os.environ['CHROMIUM_PATH']
    return playwright.chromium.launch(**options)


def to_url(target):
    return target if '://' in target else pathlib.Path(target).resolve().as_uri()


def open_page(browser, target, viewport, theme='light', scale=1, reduced_motion='no-preference',
              clicks=(), wait_ms=0, freeze=True):
    """Open TARGET and let it settle. Returns (page, info). info records what happened on the way."""
    page = browser.new_page(viewport={'width': viewport, 'height': 900}, color_scheme=theme,
                            device_scale_factor=scale, reduced_motion=reduced_motion,
                            # the page's Content-Security-Policy would block the settle style below
                            bypass_csp=True)
    info = {'status': None, 'final_url': None, 'title': None, 'warnings': [], 'clicked': []}
    response = page.goto(to_url(target), wait_until='load', timeout=GOTO_TIMEOUT_MS)
    if response is not None:
        info['status'] = response.status
    try:
        page.wait_for_load_state('networkidle', timeout=IDLE_TIMEOUT_MS)
    except Exception:  # pages that poll forever never go idle; carry on
        info['warnings'].append('network never went idle within 5 s; measured anyway')
    page.evaluate(QUIET_JS, [800, 5000])
    page.evaluate('document.fonts && document.fonts.ready')
    page.evaluate(SCROLL_JS, SCROLL_STEPS)  # make lazy-loaded content and images appear
    page.evaluate(QUIET_JS, [300, 3000])
    for selector in clicks:
        try:
            page.click(selector, timeout=3000)
            info['clicked'].append(selector)
        except Exception:
            info['warnings'].append(f'could not click {selector!r}')
    if clicks:
        page.wait_for_timeout(500)
    if wait_ms:
        page.wait_for_timeout(wait_ms)
    page.add_style_tag(content=SETTLE_CSS)
    page.wait_for_timeout(150)
    if freeze:
        page.evaluate(FREEZE_JS)
    info['final_url'] = page.url
    info['title'] = page.title()
    if info['status'] and info['status'] >= 400:
        info['warnings'].append(f'HTTP {info["status"]}: this may be an error page, not the site')
    if BLOCKED_TITLE.search(info['title'] or ''):
        info['warnings'].append(f'title {info["title"]!r} looks like a bot check or error page')
    return page, info


# The colors the page paints with. Comparing these, not screenshots, keeps rotating
# banners and other changing content from looking like a dark theme.
COLORS_JS = r'''()=>{
  const out=new Set();
  const add=(e)=>{const s=getComputedStyle(e);out.add(s.color+'|'+s.backgroundColor+'|'+s.borderTopColor+'|'+s.colorScheme)};
  add(document.documentElement); if(document.body)add(document.body);
  for(const e of document.querySelectorAll('body *'))if(e.getClientRects().length)add(e);
  return [...out].sort();
}'''


def dark_supported(browser, target, viewport, **open_kwargs):
    """True when the page paints with different colors under prefers-color-scheme: dark."""
    palettes = []
    for theme in ('light', 'dark'):
        page, _ = open_page(browser, target, viewport, theme, **open_kwargs)
        palettes.append(page.evaluate(COLORS_JS))
        page.close()
    return palettes[0] != palettes[1]


def resolve_themes(browser, target, viewport, themes, **open_kwargs):
    """Drop 'dark' when the page ignores it, so the same page is not measured twice."""
    if 'dark' in themes and 'light' in themes and not dark_supported(browser, target, viewport, **open_kwargs):
        return tuple(t for t in themes if t != 'dark'), False
    return tuple(themes), ('dark' in themes) or None
