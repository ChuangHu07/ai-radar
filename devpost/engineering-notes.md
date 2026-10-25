# AI Radar — Engineering Decisions and Known Limits

These notes document implementation choices and observed development feedback. They are not independent user-study results or a claim that every generated scientific statement is correct.

## From an idea to a bounded workflow

The original discovery target was reduced from ten to five recent papers per category query after the team found whole-batch processing burdensome. Deep reading kept its separate one-to-ten material boundary. Discovery retrieves recent work by first submission date; it does not silently become citation ranking or personalized recommendation.

The team separated resource acquisition from AI reading. A user can follow discovery into reading or enter reading directly with PDFs. The user, rather than the model, decides the final paper collection.

## Why factual checks needed more than valid JSON

A report can be structurally valid while a result number lacks support in the cited excerpt. The pipeline therefore retains original evidence identity/page locations, checks result numbers and conditions, and reviews content. It must distinguish measurements from figure labels, concept IDs, or explicitly marked teaching assumptions.

Independent model review can also be wrong. During development, both genuine formula mistakes and mistaken review findings occurred. Review findings must be reconciled with the current sentence and original evidence, rather than blindly rewriting the paper explanation until a reviewer agrees.

## Equations and repair contracts

Formula display and escaped inline math caused visible readability problems. The rendering path uses Markdown math and KaTeX. A separate controlled field-patch contract keeps equation identity and source material fixed while repairing specified explanation fields; malformed or empty patches do not become success. A formatting repair alone does not prove the equation derivation or teaching arithmetic is correct.

## First-party feedback shaped the product

- The team found road-building/geographical labels confusing. Research position now uses field, subfield, question and contribution language.
- Readers wanted novice explanations before terminology. Overview cards lead with the concrete problem and author's change.
- Abstract concept diagrams were replaced by more specific explanatory scenes, with explicit non-experimental labels.
- Repeated deep-reading action panels felt bulky. A single top-level control opens a paper list.

These are real team-driven iterations. They support a design history, not measured gains for independent users.

## Cost and failure control

The team switched from its original Claude workflow to a lower-cost configured Qwen option after experiencing usage constraints. Provider behavior, evidence contracts and caching had to remain explicit. A cheaper call is not useful if repairs repeatedly consume the saved budget.

New generation remains a paid external-provider operation. Explicit starts, compatible stage reuse, bounded repair, idempotency, cancellation, usage estimates and configured limits make that visible. Estimates are not official billing. PDF/report content is sent to the selected provider; users should only upload material they are permitted to share.

## Current limitations

- A local setup and valid provider credentials are needed for new generation; there is no production public AI endpoint.
- Normal sessions expire on backend restart; there is no persistent user library.
- No OCR for scanned PDFs; 50 MiB and 150-page per-file limits remain.
- arXiv/provider availability, long-document processing and language checks can fail visibly.
- Model-generated explanations and diagrams need human source judgment, especially equations and cross-paper comparisons.
- Reviewed examples do not establish universal accuracy, universal illustration quality, or measured time savings.
- macOS instructions are provided without hardware verification.

## Evidence still needed for a product claim

Independent participants should try the main tasks and explain a paper in their own words. Record where they fail, whether they find original evidence, and which technical terms confuse them. A small formative study can guide improvements; it cannot establish broad learning efficacy or market demand.

## Retrospective hands-on feedback

The owner subsequently reported actual software use by one team member and several non-team users. Feedback motivated illustrations for faster scanning and constraints/revisions to the initial mechanical reading structure, format and length. The later version received favorable qualitative reactions in the owner's account. See [the English record](user-feedback-2026-10-24.md) for attribution and uncertainty; no measured productivity or accuracy gain is implied.
