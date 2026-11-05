# Report format (slopscope-report/report.md)

Write in the user's language. Keep facts and opinions in separate sections. Plain words:
say "keyboard focus ring" rather than only "M-02", and explain any technical term once.

1. **Summary** (3 lines at most): how many M-checks pass, the three findings that matter most.
2. **How it was measured:** URL measured (and `final_url` if it redirected), viewports,
   themes (say so when dark was skipped because the page has none), `--click` / `--wait`
   used, and every entry in `warnings`. If a warning says the page may be a bot check or
   error page, say the results are not about the site.
3. **Measurements (fact):** one row per M-check: status, count, the worst examples with
   selector, value and threshold. Link screenshots from `shots/`. Say which M-01 findings
   are `uneven_background` and what you saw when you checked them by eye. Look at the M-02
   `weak` crops (in `focus/`) and say for each whether focus is plainly visible; list
   `caret_only` fields as advice. Neither is a failure. Say when `focus_stops_limit_reached` is true.
4. **Visual audit (opinion):** `V-0n · where · why`, one line each.
5. **Proposed direction:** 3-5 lines. Then stop and ask before editing.
6. **Not verified:** screen readers, Safari/Firefox, real devices, 200% zoom, states the
   first render does not show, iframes, plus anything the run skipped.

After a fix, add **Before / after** with the table from `scripts/compare.py` and say
whether any check regressed. Repeat any note it prints about different viewports or themes.
