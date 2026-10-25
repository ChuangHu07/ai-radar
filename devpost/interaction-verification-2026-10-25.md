# AI Radar — Interaction Evidence and Citation Fix

Date: October 25, 2026. This is a developer-operated UI check using real saved reports, not a new participant session or fresh model-generation test.

## What changed

While capturing the reading flow, activating a citation scrolled to a closed source disclosure. Readers still needed another click to see its excerpt. The shared `evidenceNavigation.ts` handler now reveals the matching excerpt and enclosing disclosures, focuses the source summary and scrolls it into view. It is used in overview cards and deep-reading Markdown. Modified clicks retain normal browser link behavior, and missing targets retain the existing anchor fallback. Report content, paper identity and generation logic are unchanged.

## Browser checks

| Action | Observed result |
|---|---|
| Open the overview's top-level reading control | Paper picker opens with no papers selected |
| Select one paper, then a second | Both remain selected and can be transferred to the reading workspace |
| Open the reading workspace | Two matching source materials are ready; joint mode appears |
| Remove the second paper | One ready material remains and single-paper mode appears |
| Click E0001 in the separate saved English joint report | Correct source disclosure opens, source excerpt is visible, keyboard focus moves to its summary, and the PDF link remains available |
| Activate E0102 with Enter | The correct second-paper source disclosure opens and receives focus |
| Click E0015 in the overview after the opening animation | Both the enclosing technical section and source disclosure open; the excerpt is visible and its summary receives focus |

The production frontend build passed after the change. The 216-test backend result from October 24 remains the last backend run; no backend source changed here. This check does not establish model accuracy, usability for every participant, or current upstream API availability.

## Supplementary video

The supplementary English interaction video shows actual browser actions with saved reports: selecting papers, editing the collection and opening original evidence. A transition explicitly identifies the separate two-paper joint report; it is not the generated result of the collection selected in the preceding segment. No generation button was pressed.

Capture uses sequential browser screenshots sampled during actual UI automation, with recorded frame timings retained. It is not a native 24-fps screen recording; 24 fps is the encoded playback rate. Cuts between segments and title cards are editorial; no UI contents or report results were fabricated. English narration is synthetic, and captions are supplied. The earlier 2:58 main video remains the primary submission video.

## User research boundary

These developer actions add evidence that the controls work. They are not additional external users, satisfaction ratings, time-saving measurements or independent validation. The [actual feedback record](user-feedback-2026-10-24.md) and its stated unknowns remain unchanged.

The final video is approximately **1:17**, 1280 × 864, with 1,854 decoded frames at 24 fps and English captions. It contains 240 sampled browser frames across the three interaction segments. Full decoding and visual checks of six timeline points completed before publication. [Watch the supplementary video](https://chuanghu07.github.io/ai-radar/#interaction-demo).
