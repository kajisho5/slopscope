# Fix playbook (only after the user says "fix")

The goal is the same page, calmer and easier to use: not a different design. Work in the
site's own stack and naming (its CSS files, Tailwind config, theme tokens, CMS theme), and
keep its brand color, typefaces, content and section order unless the user asks otherwise.

## Order

1. **Measurements that fail (M-01 to M-08).** They are facts with a threshold; fix them first.
2. **Shared values.** Use M-09 to pick a small set from what the page already uses most, then
   move stragglers onto it. This removes most of V-02 and V-03 in one pass.
3. **Visual findings (V-01 to V-09)**, most visible first. One change at a time.
4. **Measure again** into `slopscope-report/after/` and run `compare.py`. Fix every REGRESSION
   before reporting.

Change the source that generates the page (component, stylesheet, template, token), not the
built output, and not with one-off inline styles.

## Measurements

| Check | Usual fix | Watch for |
|---|---|---|
| M-01 contrast | darken the text color (or lighten it in dark) along the same hue until it passes; prefer changing the shared token over one element | placeholder and "muted" tokens are usually the culprit; check both themes |
| M-02 focus | one shared rule: `:focus-visible { outline: 2px solid <accent>; outline-offset: 2px }`; remove `outline: none` that has no replacement | the ring must reach 3:1 against the background next to it, in both themes |
| M-03 clipped ring | use `outline-offset` inward (`-2px`) inside `overflow:hidden` parents, or move the clipping to a child | carousels, cards with rounded corners |
| M-04 sideways scroll | find the element in the finding; give it `max-width: 100%`, let flex items wrap (`flex-wrap`, `min-width: 0`), wrap tables in a scroller | do not hide it with `overflow-x: hidden` on body: that cuts content instead of fitting it |
| M-05 iOS zoom | `font-size: 16px` (or `1rem`) on text inputs at small widths | never block zoom with `maximum-scale` / `user-scalable=no` |
| M-06 names | visible text first; `aria-label` for icon-only buttons; `<label>` for fields | the name should say what happens ("Close", "Search"), not what it looks like |
| M-07 targets | padding (not a bigger icon) to reach 24px, or more space between small targets | do not shrink neighbouring targets to make room |
| M-08 motion | wrap motion in `@media (prefers-reduced-motion: no-preference)`; give autoplay video a pause button and no autoplay under reduce | keep fades that carry meaning, stop loops |

## Visual findings

- **Color (V-01):** keep one accent and use it for actions. Replace decorative gradients and
  glows behind content with the site's plain background or a single tint of the brand color.
- **Spacing (V-02):** pick a scale from the page's own common values (M-09 `spacing.top`),
  e.g. 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64. Equal things get equal space; related things sit
  closer than unrelated ones.
- **Type (V-03):** at most two families and three or four sizes per screen, two weights. Body
  text 16px or more. Line length roughly 45-75 Latin characters; shorter for Japanese.
- **Icons (V-04):** one icon set, one stroke width, one size per context. Replace emoji labels
  with words or icons from that set.
- **Copy (V-05):** remove hype words and exclamation marks; say what the product does. Never
  invent numbers, customers or quotes; mark unsourced claims for the user to confirm.
- **Layout (V-06):** one primary button per view; others become secondary or links. Replace
  "generic hero" with the product's real specific claim and a real screenshot if one exists.
- **Japanese (V-08, V-09):** set the Latin font and the Japanese font so their sizes look
  matched; use half-width digits and Latin; body `line-height` about 1.7 to 1.9.

## Do not

- Do not rename the product, change its claims, or add sections, testimonials or badges.
- Do not install a new framework or design system to fix a few values.
- Do not touch a site that is not the user's own (audit it only).
