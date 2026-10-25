# AI Radar — User Validation and Evidence Status

Updated October 24, 2026. **Documented independent participant records in this release: zero.** This is a documentation count, not a claim that no sessions occurred. The owner reports that actual feedback already exists; participant context and observations have not yet been provided for this record. A study protocol is also available below. Do not describe planned sessions as completed, or team acceptance as an independent user study.

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

## Additional owner-reported feedback — details pending

On October 24, the owner stated that actual feedback already exists and requested help recording it in English. We have requested anonymous participant context, whether they used the app or viewed saved material, the actual observations, and approximate date/version if known. Independence, participant count, task outcomes and quotations are not assumed. No retroactive scores or timing measurements will be invented. The documented first-party feedback above remains valid.

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

The available evidence shows repeated first-party feedback and iterative fixes. It does **not yet demonstrate independent usability success, quantified time savings, improved comprehension, scientific accuracy, or willingness to pay**. Update this section when the owner supplies the actual feedback record or additional sessions are observed; do not infer that unrecorded feedback did not happen.
