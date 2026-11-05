---
name: slopscope
description: Audits a web page or landing page for AI-looking "slop" and for measurable usability problems, then compares before and after a fix. Two layers - a visual audit (gradients, glows, emoji labels, hype copy, uneven spacing, mixed Japanese/Latin type) written as opinion, and Chromium measurements written as fact (text contrast, visible keyboard focus, clipped focus rings, sideways scroll at 375px, iOS input zoom, unnamed controls, small tap targets, motion that ignores reduced-motion, color/size/spacing variety). Use when the user asks to audit, review or check a site, homepage, LP or UI for design quality, AI slop, accessibility basics, or regressions after a redesign. Audit-first - it proposes a direction and edits only when asked.
license: MIT
compatibility: Needs Python 3.11+, Playwright for Python and Pillow, and a Chromium build (python3 -m playwright install chromium, or CHROMIUM_PATH). Network access only for live URLs.
metadata:
  author: kajisho5
  version: "0.2.0"
---

# slopscope

Look at a page twice: once as a designer (opinion) and once as an instrument (fact).
Keep the two apart in every report. Never present an opinion as a measurement.

`SKILL_DIR` below means the folder this file is in. Run the scripts by that full path
(`python3 SKILL_DIR/scripts/measure.py ...`) from the user's project folder, so the report
lands in the project's `slopscope-report/`.

## Steps

1. **Check the tools.** `python3 -c "import playwright, PIL"`. If it fails, tell the user and
   offer `python3 -m venv .venv && .venv/bin/pip install -r SKILL_DIR/requirements.txt`
   and `.venv/bin/python -m playwright install chromium`, then use `.venv/bin/python` in place
   of `python3` below. If a Chromium is already installed elsewhere, set `CHROMIUM_PATH` to
   it instead of installing one.
2. **Target.** A URL, a local HTML file, or a project. For a project, run its dev server or
   build it and serve the output (`python3 -m http.server 8000` in the build folder), then
   use the `http://localhost:...` URL: `file://` breaks pages that load `/assets/...`.
3. **Snapshot.** `python3 SKILL_DIR/scripts/snapshot.py TARGET --out slopscope-report/shots`
   (375px and 1280px; dark only when the page supports it). Long pages are also saved as
   `-partNN.png` pieces one screen tall: look at those, not the tall image.
   **Look before going on.** If the images show
   - a cookie or newsletter banner covering the page: find its accept/close button in the
     page and re-run snapshot and measure with `--click "SELECTOR"`;
   - a bot check, login wall or error page ("Just a moment", 403, 404): stop and tell the
     user. Do not try to get around it; ask for a URL that is reachable or a local build;
   - an empty or half-drawn page: re-run with `--wait 3000`.
4. **Measure.** `python3 SKILL_DIR/scripts/measure.py TARGET --out slopscope-report/measure.json`
   (same `--click` / `--wait`). Read [references/measurements.md](references/measurements.md)
   for what each M-check means and cannot see. Read `warnings`, `dark_supported` and
   `focus_stops_limit_reached` in the JSON and repeat them in the report.
5. **Visual audit.** Judge V-01 to V-09 from the screenshots and the code, following
   [references/visual-checks.md](references/visual-checks.md). One line per finding:
   ID, where, why. If the page is already good, say so and stop at two or three refinements.
6. **Report.** Write `slopscope-report/report.md` in the user's language using
   [references/report-format.md](references/report-format.md).
7. **Stop.** End with a 3-5 line direction for the fix and wait for the user. Do not edit
   anything until they say so.
8. **Fix (only when asked, only the user's own site).** Follow
   [references/fix-playbook.md](references/fix-playbook.md). Then snapshot and measure again
   into `slopscope-report/after/` with the same options and run
   `python3 SKILL_DIR/scripts/compare.py slopscope-report/measure.json slopscope-report/after/measure.json --shots-before slopscope-report/shots --shots-after slopscope-report/after/shots`.
   A REGRESSION row means the fix broke something that passed: fix it before reporting.

## Rules

- Facts carry a number, a threshold and a selector. Opinions carry a reason. Never mix them.
- A finding marked `uneven_background` (text on an image or gradient) is a measurement you
  must confirm by eye in the screenshot before calling it a failure. M-02 `weak` entries
  come with focused/blurred crops in `slopscope-report/focus/`: look at them.
- Do not invent claims, testimonials or numbers in copy; flag existing unverified claims.
- Do not rename the product or add decoration. Do not apply one house style to every product.
- Someone else's site is audited only: measure and report, never edit or submit forms.
- Use clearly fictional names and data in any sample you write.
- Always end the report with what was not verified (screen readers, Safari/Firefox, real
  devices, 200% zoom, states the first render does not show, iframes).

## Scripts

| Script | Does | Output |
|---|---|---|
| `scripts/snapshot.py` | full-page screenshots per viewport and theme, plus one-screen pieces | `shots/<viewport>-<theme>[-partNN].png` |
| `scripts/measure.py` | M-01 to M-09 in Chromium | `measure.json` |
| `scripts/compare.py` | before/after table, screenshot differences | Markdown, exit 1 on regression |
| `scripts/slopscope_page.py` | shared loading: waits for late content, scrolls lazy content in, `--click`, `--wait` | (library) |

Both page scripts take `--viewports 375,1280`, `--themes light,dark`, `--click SELECTOR`
(repeatable) and `--wait MS`.

If Playwright or Chromium is missing and the user does not want to install it, say so, do
the visual audit from code alone, and mark every M-check as "not measured" rather than guessing.

## Credit

The visual-audit idea of naming AI-looking "tells" and fixing them in passes follows
[unslop](https://github.com/heydamir/unslop) by Damir Sokolovsky (CC BY 4.0). The wording,
checks and measurements here are written for slopscope.
