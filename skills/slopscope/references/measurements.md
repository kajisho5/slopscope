# Measurements (fact)

`scripts/measure.py` loads the page in Chromium at each viewport (default 375 and 1280px)
and color scheme, and writes `measure.json`. Each check has a threshold and findings with a
CSS selector. Selectors are unique in their page; ` >>> ` steps into a web component's
shadow root.

## How the page is loaded

The same for snapshot and measure (`scripts/slopscope_page.py`):

1. Open the page and wait for `load`, then up to 5 s for the network to go quiet and until
   the page stops changing for 0.8 s (pages drawn by JavaScript).
2. Scroll to the bottom and back so lazy-loaded content appears.
3. Click each `--click` selector (cookie banners), wait `--wait` ms.
4. End transitions at once, run animations that end (fade-ins) to their end and pause endless
   ones at their start, hide the blinking text cursor, and draw `content-visibility: auto`
   parts (Chromium leaves them blank off screen). These make two runs of an unchanged page
   identical and show it as it rests; they do not change the design. The page's
   Content-Security-Policy is bypassed so this style can be added.

Dark is measured only when the page looks different with `prefers-color-scheme: dark`
(`dark_supported` in the JSON). `warnings` lists HTTP errors, titles that look like a bot
check or error page, and clicks that failed: an audit of a bot-check page is not an audit
of the site.

## Checks

| ID | Measures | Threshold | Method | Blind spots |
|---|---|---|---|---|
| M-01 | Text contrast | 4.5:1, 3:1 for large text (WCAG 1.4.3) | screenshot of each text run at 2x; background = most common pixel, text = highest-contrast pixel | text on images and gradients is flagged `uneven_background`: confirm by eye; very thin text reads low; first 300 text runs; text off the page or clipped away is skipped |
| M-02 | Visible keyboard focus | something visibly changes on focus: 12+ pixels differ (WCAG 2.4.7 AA) | Tab through up to 60 stops, compare crops focused and blurred | only stops reachable from the first render. Stops that change but where no 12 pixels change by 3:1 (the 2.4.13 AAA test) are listed in `weak` with crops in `focus/`: judge them by eye. Text fields whose only indicator is the text cursor are in `caret_only` (WCAG 2.4.7 accepts the cursor). Neither fails |
| M-03 | Clipped focus ring | outline or shadow not cut by an ancestor with hidden/clipped overflow | computed outline/shadow extent vs ancestors | does not see clipping by other elements painted on top |
| M-04 | Sideways scroll | the page cannot be scrolled sideways at the narrowest viewport | asks the browser to scroll right; lists the outermost elements that stick out | content cut off by `overflow-x: hidden` on body is not a scroll and is not reported |
| M-05 | iOS input zoom | text inputs at 16px or more at the narrowest viewport | computed font-size | Safari itself is not run |
| M-06 | Accessible names | every interactive element has a name | Chromium accessibility tree | names are present, not necessarily good |
| M-07 | Target size | 24x24px or more, or spaced so a 24px circle on its centre touches no other target (WCAG 2.5.8 AA); inline links in a line of other text exempt; a control's label counts as part of it | bounding boxes and the spacing test (a link wrapped onto two lines counts as its two line boxes); hidden and off-page targets skipped | equivalent-control and essential exceptions are not judged |
| M-08 | Reduced motion | no infinite animation and no autoplaying video with prefers-reduced-motion: reduce | document.getAnimations(), playing `<video>` | JavaScript-driven motion (requestAnimationFrame, canvas) is not seen |
| M-09 | Variety (info) | none; reference only | counts distinct text colors, backgrounds, font sizes and spacing values | a count is not a judgment |

Statuses: `pass`, `fail`, `info` (M-09). M-01 also has `by_colors`: failing text grouped by
color pair, which usually points at one shared color to change. `not_verified` in the JSON lists what no check covers,
including iframes and closed shadow roots.

Large text: 24px and up, or 18.66px and up at weight 700.
