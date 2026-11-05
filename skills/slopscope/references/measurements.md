# Measurements (fact)

`scripts/measure.py` loads the page in Chromium at each viewport (default 375 and 1280px)
and color scheme (light, dark), with animations paused at their start, and writes
`measure.json`. Each check has a threshold and findings with a CSS selector.

| ID | Measures | Threshold | Method | Blind spots |
|---|---|---|---|---|
| M-01 | Text contrast | 4.5:1, 3:1 for large text (WCAG 1.4.3) | screenshot of each text run at 2x; background = most common pixel, text = highest-contrast pixel | text on images and gradients reads per pixel; very thin text reads low; first 300 text runs |
| M-02 | Visible keyboard focus | at least 12 pixels change by 3:1 between focused and blurred (WCAG 2.4.7, 1.4.11) | Tab through up to 40 stops, compare crops | only stops reachable from the first render |
| M-03 | Clipped focus ring | outline or shadow not cut by an ancestor with hidden/clipped overflow | computed outline/shadow extent vs ancestors | does not see clipping by other elements painted on top |
| M-04 | Sideways scroll | no horizontal scroll at the narrowest viewport | elements whose right edge passes the viewport and are not inside a scroller | only the first render |
| M-05 | iOS input zoom | text inputs at 16px or more at the narrowest viewport | computed font-size | Safari itself is not run |
| M-06 | Accessible names | every interactive element has a name | Chromium accessibility tree | names are present, not necessarily good |
| M-07 | Target size | 24x24px or more (WCAG 2.5.8 AA); links inside sentences exempt | bounding boxes | the spacing exception is not applied |
| M-08 | Reduced motion | no infinite animation running with prefers-reduced-motion: reduce | document.getAnimations() | JavaScript-driven motion (requestAnimationFrame, video) is not seen |
| M-09 | Variety (info) | none; reference only | counts distinct text colors, backgrounds, font sizes and spacing values | a count is not a judgment |

Statuses: `pass`, `fail`, `info` (M-09). "not_verified" in the JSON lists what no check covers.

Large text: 24px and up, or 18.66px and up at weight 700.
