# AI Radar — Final Competition Review

Reviewed October 24, 2026 against the [official rules](https://learn-ai-basics.devpost.com/rules). This is a team audit, not an organizer decision, score or prediction. Source under test: public repository commit `0c081f9`; subsequent changes in this review update presentation and verification records, not the application pipeline.

## What a reviewer can inspect

| Official criterion | Concrete evidence | Remaining limitation |
|---|---|---|
| Design | Category discovery → overview → top-level selection → editable materials → reading → source excerpts. [Video at 1:10](https://www.youtube.com/watch?v=1sG9wfRfSuk&t=70s). | The demonstration uses saved outputs; session history is temporary. |
| Potential impact | A specific first task: help researchers/students approaching unfamiliar work understand the problem and decide what to read next. Actual hands-on feedback led to illustrations and revised report structure. | Feedback is retrospective and qualitative. Exact external count, individual tasks and measured outcomes were not collected. |
| Innovation / idea | Consistent novice-first explanation, concrete scenes, deliberate single/joint selection and original evidence inspection in one workflow. [Video at 0:50](https://www.youtube.com/watch?v=1sG9wfRfSuk&t=50s). | This is a product/workflow contribution, not a new model or a claim that no other research tool has these features. |
| Presentation | English 2:58 video, captions, four real application screenshots, chapter links, public code and current English planning. [Evidence view at 1:53](https://www.youtube.com/watch?v=1sG9wfRfSuk&t=113s). | The video is an edited sequence of real views, not an uninterrupted recording of a fresh end-to-end generation. The separate joint example is disclosed. |

## Verification performed in this review

- Public repository backend suite: **216 passed in 6.88 seconds** on Windows using Python 3.12.14 and the existing project virtual environment.
- Command: `python -m pytest tests -q --basetemp=.local-data/pytest-award-audit-20261024-a --junitxml=.local-data/award-audit-tests.xml`.
- The initial run had 205 passes and 11 fixture-setup errors because an existing Windows system temporary directory denied access. A new workspace-local temporary directory resolved all 11; no assertions or tests were removed.
- Frontend: fresh locked dependency installation using `npm ci --ignore-scripts --no-audit --no-fund`, followed by successful `npm run build` (TypeScript and Vite). Initial build without installed dependencies could not find `tsc`.
- The main JavaScript bundle is approximately 712 kB before gzip / 217 kB gzipped. Vite reports a nonblocking size warning. This review does not claim a performance benchmark or dependency vulnerability audit.
- Tests use synthetic data and mocked model calls. No new paid model generation, full scientific review, clean-machine backend installation or macOS hardware test was performed in this review.

## Submission improvements

- Made the audience's first decision explicit: whether a paper deserves deeper reading and why.
- Explained the integrated workflow using the demonstrated tool-failure scene and separate source-inspection example.
- Added timestamped navigation to the existing video so readers can find the demonstrated features quickly.
- Updated stale verification dates while preserving distinctions between automated checks, actual generated samples and owner-reported feedback.
- Kept [the feedback record](user-feedback-2026-10-24.md) tied to the supplied account; no invented users, quotations, measurements or market demand.

## Remaining opportunities, in order of value

1. A short continuous capture of a representative user interaction would provide stronger interaction evidence than edited still views. A fresh generation could include a clearly labeled waiting-time cut. Current video remains within the required duration and honestly identifies saved reports.
2. Optional follow-up users could explain one paper in their own words, find its evidence and select a reading collection. Record their actual outcomes and confusion before claiming time savings or learning benefits. Do not retroactively assign scores to the existing feedback.
3. Durable saved libraries and more sources are future product hypotheses. Validate demand before expanding the prototype.

Cloud hosting is deferred at the owner's request. The required public repository and accessible video are supplied. Neither more spending nor more features guarantees an award; the organizer determines eligibility and ranking.
