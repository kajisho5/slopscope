# Report format (slopscope-report/report.md)

Write in the user's language. Keep facts and opinions in separate sections.

1. **Summary** (3 lines at most): how many M-checks pass, the three findings that matter most.
2. **Measurements (fact):** one row per M-check: status, count, the worst examples with
   selector, value and threshold. Link screenshots from `shots/`.
3. **Visual audit (opinion):** `V-0n · where · why`, one line each.
4. **Proposed direction:** 3-5 lines. Then stop and ask before editing.
5. **Not verified:** screen readers, Safari/Firefox, real devices, 200% zoom, states the
   first render does not show, plus anything the run skipped.

After a fix, add **Before / after** with the table from `scripts/compare.py` and say
whether any check regressed.
