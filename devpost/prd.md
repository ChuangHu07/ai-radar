---
doc: prd
status: approved-product-requirements
edition: current-English-consolidation
updated: 2026-10-24
---

# AI Radar — Product Requirements

This is the English current-state consolidation of the approved requirements and accepted feedback. Historical proposals and superseded limits are not presented as current requirements. Requirements describe expected behavior; the [delivery checklist](checklist.md) separates recorded verification from independent user validation.

## 1. Users and outcome

For a researcher or student entering an unfamiliar field, the first useful outcome is understanding **what problem a paper tackles, what the authors changed, and what the evidence actually shows**. Deep reading then provides a structured learning path. No personal background, prior-knowledge, or learning-goal form is required.

## 2. Screens and navigation

### Opening and homepage

- A branded AI Radar animation lasts approximately one to three seconds on a fresh opening and can be skipped by clicking. Internal navigation does not replay it.
- Use the approved dimensional-layering direction: pale blue-gray background, dark text, blue-purple accents, rounded cards, and restrained shadows/motion. Decoration must not obscure reports or errors.
- Place category search at the center, with custom category shortcuts and official monthly submission rankings below it. A top-level entry opens the deep-reading workspace directly.
- Search official names/codes and supported aliases. Show candidates for ambiguous input; do not silently ask AI to choose the research field.
- Custom shortcuts start empty with an add prompt and persist after reopening. Ranking availability does not block search or shortcuts.

### Overview

- Category selection starts discovery and overview generation, except where unavailable sources require a user decision.
- Show a brief batch introduction and up to five paper cards in retrieval order. Show actual count, retrieval/date meaning, original title, identifier, category, source, and reading basis.
- Keep deep reading in one top-level control. Clicking it opens a compact list for selecting one or several papers; avoid a large repeated action panel on every card.
- A selected paper must retain its identity and source when passed to the reading workspace.

### Reading workspace and reports

- Accept selected overview papers and uploaded PDFs in one editable list.
- Users can add, remove, or replace materials before generation. Replacement updates the existing material rather than creating an extra paper.
- Clearly display readiness and specific failures for each material.
- **Generate Report** is enabled only for one to ten ready materials. Adding a paper or finishing an upload never automatically starts deep reading.
- One material selects single reading; two to ten select joint reading. Do not choose a related-paper cluster automatically.
- During generation show progress and prevent duplicate starts. On completion show the structured report, source references, and PDF evidence inspection.

## 3. Discovery and monthly rankings

The first release uses only arXiv. Freeze a runtime cutoff, sort by first submission date, deduplicate versions by paper identity, and return at most five distinct papers. Keep update dates separate from first submission dates.

- One to four results: generate for the actual count without inventing or backfilling papers.
- Zero results: show **No papers found** and do not generate a report.
- Network/source error: report that error; do not mislabel it as an empty search.
- Full text unavailable but abstract available: pause and show the paper and reason. The user may explicitly continue with an **abstract-only overview** or remove it. Do not silently fall back.
- Neither full text nor abstract available: allow removal or exit; do not generate unsupported content.
- Removing every paper leaves no report to generate. Removing one paper does not automatically retrieve a replacement.

Rankings use the latest valid official statistics month and archive-level submission totals. Show the actual month; a missing month is not a zero count. They are not popularity rankings. Official statistics groups map to their correct search-category unions; exact subcategory search remains separately supported.

If no valid ranking data exists, hide that section while preserving an external manual-fetch control and attempt status. Automatic fetching has at most three total attempts, including the first; success stops retries. Persist used attempts across restarts. Manual fetching performs one attempt and does not restart an endless automatic cycle. A verified older snapshot may be displayed with its true month and snapshot label.

## 4. Overview output contract

### Batch introduction

Use at most a few concise sentences to explain the problems represented by this batch. A Chinese target of about 120 characters is a writing goal, not a reason to drop necessary conditions; English should have comparable density. Do not claim these five papers exhaust an entire field or force unrelated papers into one trend.

### Paper cards

The collapsed reading order is:

1. Plain-language title, while retaining the official paper title.
2. A specific explanatory scene when a reviewed, paper-matched illustration is available.
3. **Understand first**: two or three sentences explaining the situation, previous obstacle, the author's change, and intended outcome.
4. Precise broad-to-narrow research position.
5. One technical explanation, contribution type, and reading guidance.

Expanded content explains the problem, approach, observed effect, significance, and limitations. Shortness is a soft target; fixed sections, evidence identity, numerical conditions, and usability are hard constraints. Necessary terms must be explained on first use. Avoid obscure geographical labels or road-building categories.

Illustrations are labeled **Concept illustration — not an original paper figure or experimental result**, with English/Chinese descriptions and alternative text. They must not introduce unsupported numerical or mechanism claims. Unknown papers receive no unrelated decorative scene. The current reviewed scene coverage is limited; universal paper illustration is not claimed.

## 5. Single-paper reading contract

| Section | Reader outcome |
|---|---|
| Quick reading card | Identify the main problem, contribution, result, and learning outcome |
| Research position and contribution | Follow field → subfield → topic → problem/route → this contribution, including relevant distinctions |
| Before you read | Review a layered prerequisite map, self-checks, dependencies, and optional routes |
| Core idea | See a concise explanation, bounded analogy, and technical description |
| Method | Follow data flow, component purpose, design questions, concept cards, and pseudocode when supported |
| Equations | Explain symbols, terms, intuition checks, and labeled teaching examples; omit the section when no reliable core equation is available |
| Reading experiments | Relate claims to evidence, conditions, tables, strength, limitations, and reproduction requirements |
| Value | Separate academic value, potential application, author limitations, and explicitly labeled AI interpretation |
| Self-check | Try layered questions, reference answers, and a teach-back challenge |
| Further reading | Use verified predecessor names or search keywords and a glossary; do not invent resource links |

Offer one layered guide without forcing a background form. Readers can skip familiar concepts or expand technical explanations. Background knowledge, author claims, AI interpretation, and teaching assumptions must be distinguishable. PDF equation transcription is not original LaTeX. Do not invent HTML anchors, tables, or missing evidence.

## 6. Joint-reading contract

Joint reading has six sections rather than ten duplicated single-paper guides:

1. **Shared scope**: explain a common question and each paper's entry point; say when common ground is weak.
2. **Shared knowledge and concept differences**: explain common prerequisites once and distinguish different definitions/conditions.
3. **Research routes**: compare what each paper changes and how the methods differ.
4. **Evidence and results**: retain paper-specific sources, tasks, datasets, metrics, and conditions. Explicitly say when direct comparison is invalid; do not invent a common ranking.
5. **Complementarity, disagreement, and limits**: distinguish author conclusions from cross-paper inference. Publication order alone does not prove improvement.
6. **Combined learning takeaways**: relate concepts/methods and identify evidence gaps without becoming an autonomous research-design service.

Every selected paper remains identifiable in the report. Joint generation requires every material in the final list to have available, parseable full text. Never skip failures, replace them with abstracts, or publish a partial joint report as complete.

## 7. Materials, failures, and recovery

| Situation | Expected behavior |
|---|---|
| Empty collection | Disable generation and explain how to add papers |
| More than ten papers | Reject the over-limit addition as a batch; retain the original collection |
| Invalid, encrypted, oversized, over-page-limit, or textless PDF | Show the specific failure; allow replacement or removal |
| Replacement | Preserve item identity, record uploaded content as the actual source, re-parse, and recheck readiness |
| One failed paper among otherwise ready papers | Keep generation blocked until the user fixes or removes it |
| All final materials ready | Enable the explicit generation button; do not auto-start |
| Report or language generation fails | Show reason and **Regenerate / Exit** |
| Regenerate | Reuse the confirmed materials, language, and compatible completed stages; still recheck readiness |
| Exit | End that generation flow and retain the current page for editing; late responses must not overwrite the abandoned view |
| Backend restarts | Explain that normal paper/report sessions expire; do not imply durable report storage |

File limits are 50 MiB and 150 pages per PDF. Text extraction and material readiness do not prove every figure, equation, or claim has been interpreted correctly. OCR is excluded.

## 8. Interface and report languages

- Interface: Chinese or English. Reports: Chinese, English, or bilingual.
- Default both to Chinese on first use and remember choices independently.
- Interface translation covers navigation, controls, status, and error explanations. Preserve original paper titles, codes, and links.
- Interface switching does not trigger a model call or change existing report content.
- Changing the language of an existing report starts the corresponding language job without a second confirmation, using the same material/evidence/fact basis. This may cost money and take time; it is not instantaneous translation.
- First deep-reading generation still requires the button and all materials ready.
- Bilingual output aligns section by section; facts, conditions, numbers, citations, and missing-information notices must remain consistent. Failure uses the normal regenerate/exit controls.

## 9. Acceptance and evidence boundaries

The source and team acceptance records cover normal discovery/reading flows, mixed collections, failure recovery, category shortcuts/rankings, English UI, and three report languages. Specific samples and limits are summarized in [checklist.md](checklist.md). Do not treat the existence of a requirement, a checkbox, a unit test, or a saved screenshot as proof of independent user benefit.

Feedback documentation and an optional independent validation protocol are maintained separately. The optional protocol focuses on comprehension, navigation, and evidence inspection. No participant count, time saving, accuracy gain, or success rate is reported without an actual recorded observation.

## 10. Out of scope and website follow-up

No OCR, automatic clusters, multi-provider discovery, accounts, production hosting, subscriptions, saved libraries, or personalized curriculum is included. Website integration and cloud hosting are deferred at the owner's request; they are not a blocker for this submission revision. A public demo player is already available; it must not be described as a deployed inference service.
