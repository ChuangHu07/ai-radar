# AI Radar — User Validation and Evidence Status

Updated October 24, 2026. The owner has now provided an account of hands-on feedback involving **one team member and several non-team users**. All described participants operated the software, according to the owner. The exact external/total count, dates, backgrounds and individual task records were not provided. This is qualitative retrospective feedback, not a controlled independent study. See the [anonymized English feedback record](user-feedback-2026-10-24.md).

## Existing evidence: first-party formative feedback

The project owner is a member of the two-person development team and also tried the tool as an intended user. The following observations are recorded in the project's development conversation/acceptance notes. They are qualitative, first-party observations; no task timings or numerical comprehension scores were collected.

| Recorded feedback | Design response | What it does not prove |
|---|---|---|
| Research-type road-building language and geographical labels were confusing | Use precise field-to-contribution positioning | Comprehension for all novice readers |
| The overview remained too technical for a reader without field background | Put a concrete problem and change before technical wording | A measured learning improvement |
| Initial illustrations were too abstract | Replace the reviewed examples with paper-specific concrete scenes | That every generated illustration is accurate or helpful |
| Repeated per-paper deep-reading panels felt bulky | Move selection to a top-level control and compact picker | Faster navigation for independent participants |
| Formula source text sometimes displayed incorrectly | Improve the math rendering/repair path and inspect examples | Mathematical correctness of every model derivation |
| The owner explicitly accepted later visual and English samples | Record those sample-specific acceptances | An external success rate or market validation |

The owner's stated learning outcome was clarifying an initially vague idea, describing requirements precisely, and decomposing a large feature into manageable parts. It is a self-report, not a formal skills assessment.

## Additional hands-on feedback — recorded October 24

The owner's account identifies three stages:

1. **Text-only overview:** users wanted a faster, more efficient scan, motivating visual explanations.
2. **Initial deep reading:** a team member found the report mechanical and not practically useful. The team constrained the framework and revised format, length and generation requirements through repeated review.
3. **Final version:** the owner reported shared positive views on the maturity and research usefulness of the content/framework, and on illustrations as concise visual summaries.

The [full feedback record](user-feedback-2026-10-24.md) distinguishes participant context, changes and evidence limits. These are English paraphrases of the owner's account; no identifying or invented direct quotations are presented. Non-team participation is reported, but comments are not attributed individually and no numerical outcome is inferred. Actual use did not necessarily mean a fresh model generation in every session; that detail was not recorded.

## Optional further independent study protocol

### Goal and participants

Start with a small formative study, ideally including readers unfamiliar with the demonstrated research area. Recruit actual volunteers; record their background in broad anonymous categories and whether they are on the development team. Do not count a developer acting as a user as independent validation.

There are two different study types:

- **Walkthrough comprehension**: use the public English video/screenshots. This can test whether explanations are understandable. It cannot test live navigation, generation reliability or response time.
- **Interactive usability**: use an actually running local or hosted app, preferably with a clearly identified saved-report fixture for consistency. This can test operations. Record whether a task reused a saved report or performed paid live generation.

Do not blend results from the two types into one success rate.

### Consent and privacy

Explain the prototype purpose and voluntary nature. Obtain consent before notes/recording and separately before publishing quotations or screenshots. Use anonymous participant IDs. Do not collect passwords, API keys, employer documents, unpublished research or other sensitive files. A facilitator should operate the configured provider account rather than asking participants to paste credentials.

### Tasks and neutral prompts

| Task | Prompt | Observation |
|---|---|---|
| Find a field (interactive only) | Find artificial intelligence using the category search | Correct category chosen; hint level; confusion |
| Understand one overview card | Explain the previous problem, the authors' change, and one limitation in your own words | Compare answer to a facilitator-checked source-based rubric |
| Interpret the illustration | Explain what the three steps mean and whether the picture is an experimental result | Misinterpretations and unsupported inferences |
| Choose papers (interactive only) | Choose one paper for deep reading, then show where to add another PDF | Picker found; correct paper identities; mode understood |
| Inspect evidence | Show where a particular claim comes from and identify its paper/PDF page | Correct excerpt identified; distinguish quote from AI explanation |
| Recover a failure (interactive only) | A material is unavailable; show what you would do before generating | Replace/remove understood; no expectation of silent skipping |
| Language control (interactive only) | Keep the interface English and request a bilingual report | Interface/report controls distinguished; cost/wait understood |

For timing, start/stop at declared task boundaries. Mark success as unassisted, assisted, or incomplete; do not silently count facilitator help as unassisted success. Do not trigger extra paid generation without the owner's agreed session budget.

### Comprehension rubric

Before a session, the facilitator checks one target paper against its source and records expected problem, method/change, evidence condition and limitation. Score each answer 0 (missing/incorrect), 1 (partial), or 2 (substantially correct). Keep the original answer and notes. This rubric describes the protocol; no scores have yet been observed.

An optional before/after comparison must use the same paper, equal reading time and a declared order; acknowledge practice/order effects. A small convenience sample cannot prove general learning gains or broad time savings.

### Recording and reporting

Use [the blank CSV](user-validation-template.csv). Keep personal/contact details and raw consent records out of the public repository. Publish only consented, anonymized summaries.

A completed report should state the actual date, participant count/background, task type, exact app/report version, live-versus-saved status, assistance, outcomes, key quotations with consent, failures, resulting changes and limitations. Do not fill missing observations with expected outcomes. Report honest null/negative results too.

## Current conclusion

The record supports a qualitative feedback-driven design history, with owner-reported hands-on involvement from both team and non-team users and favorable feedback on the later version. It does **not establish quantified time savings, improved comprehension, scientific accuracy, task success rates or market demand**. Exact participant counts and per-user attribution remain unknown. The optional protocol above is future work and must not be presented as a procedure used for these past sessions.


## October 25 developer checks — separate evidence

No new external users were recruited. The [October 25 developer evaluation](developer-evaluation-2026-10-25.md) records a fresh five-paper acquisition (137 pages), a signed-number repair failure and its explicit cached recovery, a same-model/same-PDF direct-chat comparison, and task-based checks in the actual frontend. These checks do not measure human comprehension, time savings or market demand. The original retrospective feedback is unchanged.
