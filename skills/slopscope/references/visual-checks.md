# Visual checks (opinion)

Judge each from the screenshots first (the `-partNN.png` pieces for long pages), then
confirm in code. Write one line per finding:
`V-0n · where · why`. Skip an ID when nothing applies. These are judgments; say so.

| ID | Look for | Typical tells |
|---|---|---|
| V-01 | Color | hue gradients behind content, glows, colored shadows, gradient text, more than one accent, accent used for decoration instead of action |
| V-02 | Spacing | equal things spaced unequally, values off a 4px grid, cramped groups next to empty bands, edges that almost line up but do not |
| V-03 | Type | many weights, tight letter-spacing on small text, all-caps tracked labels, decorative fonts for UI, body lines far too long to read at 1280px |
| V-04 | Icons | emoji used as labels or bullets, mixed icon sets, mixed stroke widths or sizes |
| V-05 | Copy | exclamation marks, hype words (revolutionary, next-gen, supercharge), greeting headlines, numbers with no source ("10,000+ teams") |
| V-06 | Layout | two or more primary buttons, generic hero that would fit any product, dead bands, card grids of identical boxes, stretched or blurry images, a 375px layout that is just the desktop one squeezed |
| V-07 | Motion | looping or pulsing elements, bounce, entrance animation on every block |
| V-08 | Japanese/Latin mix | Latin and Japanese glyphs at visibly different sizes or weights, full-width and half-width digits or symbols mixed |
| V-09 | Japanese line height | body text in Japanese below about 1.6 line-height, or long lines without enough leading |

The template test: would this page still work if another product's name replaced this one?
If yes, say which parts make it generic.

Use M-09 as a hint, not a verdict: many distinct spacing or font-size values often show
where V-02 and V-03 come from.

A page with no findings is a valid result. Do not invent problems to fill the list.
