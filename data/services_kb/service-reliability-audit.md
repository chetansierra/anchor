# Agent reliability audit

**Service id:** reliability_audit · **Typical price:** $500+ (premium, scoped to your bot)

You already have an AI chatbot or agent — built in-house or with a no-code tool — and you're not sure it's safe to trust. I run my **evaluation harness** against it to find where it hallucinates, gives wrong answers, calls the wrong tool, or fails to refuse out-of-scope questions, and hand you a report with numbers and concrete fixes.

## When this fits

- You have a live bot and need evidence it's accurate before you scale it or expand who sees it.
- Stakeholders ask "how do we know it won't make something up?" and you have no measured answer.
- You want an independent check, separate from whoever built it.

## What's included

- A labeled test set over your domain, including out-of-scope questions it *should* refuse.
- Automated scoring: retrieval hit-rate, answer correctness (LLM-as-judge with a rubric), and tool-call correctness (right tool, right arguments).
- A report: overall accuracy %, a breakdown by failure category, and a prioritized list of fixes.
- Optional: I implement the top fixes and re-run the eval to show the lift.

## Why this is rare

Almost no freelancer ships evaluation numbers. The Nimbus case study on this site is the format: 92.7% overall accuracy, 100% retrieval hit-rate, and 8/8 correct refusals on out-of-scope questions — measured, not asserted.
