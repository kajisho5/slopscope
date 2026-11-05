---
name: slopscope
description: Audits a web page or landing page for AI-looking "slop" and for measurable usability problems, then compares before and after a fix. Two layers - a visual audit (gradients, glows, emoji labels, hype copy, uneven spacing, mixed Japanese/Latin type) written as opinion, and Chromium measurements written as fact (text contrast, visible keyboard focus, clipped focus rings, sideways scroll at 375px, iOS input zoom, unnamed controls, small tap targets, motion that ignores reduced-motion, color/size/spacing variety). Use when the user asks to audit, review or check a site, homepage, LP or UI for design quality, AI slop, accessibility basics, or regressions after a redesign. Audit-first - it proposes a direction and edits only when asked.
license: MIT
compatibility: Needs Python 3.11+, Playwright for Python and Pillow, and a Chromium build (python3 -m playwright install chromium, or CHROMIUM_PATH). Network access only for live URLs.
metadata:
  author: kajisho5
  version: "0.1.0"
---

# slopscope

Look at a page twice: once as a designer (opinion) and once as an instrument (fact).
Keep the two apart in every report. Never present an opinion as a measurement.

## Steps

1. **Target.** Take a URL or a local HTML file / project. If it is a project, build or
   serve it first and use the local URL. Write everything to `slopscope-report/`.
2. **Snapshot.** `python3 scripts/snapshot.py TARGET --out slopscope-report/shots`
   (375px and 1280px, light and dark). Look at the images before reading code.
3. **Measure.** `python3 scripts/measure.py TARGET --out slopscope-report/measure.json`.
   Read [references/measurements.md](references/measurements.md) for what each M-check
   means and what it cannot see.
4. **Visual audit.** Judge V-01 to V-09 from the screenshots and the code, following
   [references/visual-checks.md](references/visual-checks.md). One line per finding:
   ID, where, why. If the page is already good, say so and stop at two or three refinements.
5. **Report.** Write `slopscope-report/report.md` in the user's language using
   [references/report-format.md](references/report-format.md).
6. **Stop.** End with a 3-5 line direction for the fix and wait for the user. Do not edit
   anything until they say so.
7. **Fix (only when asked).** Keep the product, its features, its content and its section
   order. Fix measurements first, then visual findings. Then snapshot and measure again into
   `slopscope-report/after/` and run
   `python3 scripts/compare.py slopscope-report/measure.json slopscope-report/after/measure.json --shots-before slopscope-report/shots --shots-after slopscope-report/after/shots`.
   A REGRESSION row means the fix broke something that passed: fix it before reporting.

## Rules

- Facts carry a number, a threshold and a selector. Opinions carry a reason. Never mix them.
- Do not invent claims, testimonials or numbers in copy; flag existing unverified claims.
- Do not rename the product or add decoration. Do not apply one house style to every product.
- Use clearly fictional names and data in any sample you write.
- Always end the report with what was not verified (screen readers, Safari/Firefox, real
  devices, 200% zoom, states the first render does not show).

## Scripts

| Script | Does | Output |
|---|---|---|
| `scripts/snapshot.py` | full-page screenshots per viewport and theme | `shots/<viewport>-<theme>.png` |
| `scripts/measure.py` | M-01 to M-09 in Chromium | `measure.json` |
| `scripts/compare.py` | before/after table, screenshot differences | Markdown, exit 1 on regression |

If Playwright or Chromium is missing, say so, do the visual audit from code alone, and mark
every M-check as "not measured" rather than guessing.

## Credit

The visual-audit idea of naming AI-looking "tells" and fixing them in passes follows
[unslop](https://github.com/heydamir/unslop) by Damir Sokolovsky (CC BY 4.0). The wording,
checks and measurements here are written for slopscope.
