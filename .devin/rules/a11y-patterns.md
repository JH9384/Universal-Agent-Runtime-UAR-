---
description: Accessibility patterns for operator-dashboard React components
globs: apps/operator-dashboard/src/**/*.tsx
---

# Accessibility (a11y) Rules

## Buttons

- Every `<button>` that does NOT submit a form MUST have `type="button"`.

- Rationale: Without `type="button"`, a button inside any future `<form>` wrapper will submit the form instead of triggering its `onClick`.

- Exception: Buttons explicitly intended to submit or reset a form may use `type="submit"` or `type="reset"`.

## Decorative Visual Elements

- Purely decorative elements (e.g., status dots, color swatches, icons without labels) MUST have `aria-hidden="true"`.

- Rationale: Empty decorative spans are traversed by screen readers and create noise. The adjacent textual label (status badge, name, etc.) already conveys the meaning.

- Pattern: `<span className="mc-dot" aria-hidden="true" />` is correct; `<span className="mc-dot" />` is incorrect.

## Dynamic Polling Content

- Status summaries that update automatically via polling (e.g., counts, health states) SHOULD use `aria-live="polite"`.

- Rationale: Screen-reader users are notified when data changes without requiring them to manually re-read the page.

- Apply to: header counts, circuit-breaker summaries, health status indicators.

- Do NOT apply to: static labels, user-triggered filter results that update immediately on interaction.

## Summary Checklist

- [ ] All non-submit `<button>` elements have `type="button"`.

- [ ] All decorative `.mc-dot` spans have `aria-hidden="true"`.

- [ ] Polling status summaries have `aria-live="polite"`.
