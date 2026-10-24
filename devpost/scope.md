---
doc: scope
status: approved-product-scope
edition: current-English-consolidation
updated: 2026-10-24
---

# AI Radar — Project Scope

This English edition consolidates the team's approved scope and subsequent accepted changes. It describes the submitted proof of concept, rather than replaying every historical planning note. It does not assert that every target has been independently user-tested. Original planning records are retained in the development workspace and earlier repository history. See [PRD](prd.md), [technical specification](spec.md), and [delivery evidence](checklist.md).

## Problem and audience

Finding a recent paper and understanding it are separate tasks. Researchers and students entering an unfamiliar STEM field need a clear explanation of what a paper does, which problem it addresses, and what evidence supports its conclusions. AI Radar provides an accessible first overview and an optional route to deeper study.

## The unique kernel

One connected workflow: **official arXiv category → recent-paper overview → user-selected papers → single or joint reading → original source excerpts and PDF pages**.

The two AI modes have consistent structures. Readers should not have to repeatedly design prompts. Plain-language explanations come before technical details; evidence and limitations remain visible.

## Core journey

1. Open the app, skip or watch the brief branded introduction, and search for an official category by name or code. No background questionnaire is required.
2. Select a category. Retrieve up to five distinct papers, ordered by first submission date, with the retrieval-time cutoff recorded. A category group searches the mapped union of its official subcategories.
3. Generate a concise frontier overview. For unavailable full text, first ask the user to remove that paper or explicitly accept an abstract-only overview when an abstract exists. Never silently substitute an abstract for full-paper reading.
4. Use the overview's top-level deep-reading control to open a compact paper picker. The user chooses which papers to study; no cluster is selected automatically.
5. In the independent reading workspace, remove papers, upload PDFs, or replace failed materials. Users can also enter this workspace directly from the homepage.
6. Click **Generate Report** when all final materials are ready. One paper starts single-paper reading; two to ten start joint reading.
7. Read the structured report and follow evidence references to source excerpts and physical PDF pages. Generation failures show an actual reason and explicit retry/exit actions.

## Proof-of-concept boundary

| Area | Included |
|---|---|
| Discovery source | Official arXiv API and official category taxonomy; no Google Scholar integration |
| Discovery batch | At most five recent distinct papers; fewer results are valid; zero results produce a visible no-papers error |
| Date meaning | First submission date determines recency; version-update dates are separate |
| Sources for deep reading | Retrieved papers and user-uploaded PDFs in one editable collection |
| Collection size | One paper for individual reading; two to ten for joint reading |
| PDF limits | At most 50 MiB and 150 pages per extractable-text PDF; no OCR |
| Generation control | Automatic overview after category selection, except required source decisions; explicit button for first deep-reading generation |
| Failure handling | Failed deep-reading materials must be replaced or removed before generation; no silent partial joint report |
| Languages | Chinese/English interface; Chinese, English, or bilingual reports, selected independently |
| Preferences | Remember language choices and custom category shortcuts |
| Monthly ranking | Official archive-level submission counts, with the actual statistics month; not visits, citations, downloads, or popularity |
| Runtime | Local Python backend and browser frontend; Windows verified; macOS setup documented but hardware validation optional and unperformed |

The earlier ten-paper discovery target was reduced to five by the team on October 6. The independent ten-paper deep-reading limit did not change. On October 16, the team made macOS hardware testing optional. Neither historical target overrides this edition.

## Output and trust requirements

- Overview: a brief batch introduction followed by ordered paper cards. Each card first explains a concrete problem and the author's change in plain language, then gives research context, technical wording, results, significance, and limitations.
- Single reading: a layered learning guide covering the research position, prerequisites, core idea, method, equations when supported, experiments, value, self-checks, and further-reading terms.
- Joint reading: compare shared scope, concepts, research routes, evidence under their original conditions, relationships/limitations, and combined learning takeaways.
- Position research using precise field → subfield → problem → contribution language. The early geographical and road-building metaphors were replaced after team feedback.
- Concept illustrations explain mechanisms or situations. They are labeled as explanatory illustrations, not original paper figures or experimental evidence. Unmatched papers must not receive an unrelated generic illustration.
- Preserve original paper titles, identifiers, links, numerical conditions, source identity, and reading coverage. Distinguish author claims, AI interpretation, and teaching examples.
- Structural/evidence checks and model review help catch failures; they do not certify scientific correctness. Important claims and equations still require source inspection.

## What working means

A reviewer can see actual application views and generated reports covering category discovery, a five-paper overview, paper selection, PDF materials, joint reading, and source evidence. The English demonstration uses real saved reports and explicitly identifies its separate joint-reading example. Waiting time is omitted; it is not presented as a fresh uninterrupted inference session.

The submitted source has run/setup instructions, dependency locks, tests, and these planning documents. The public GitHub Pages site hosts the demonstration video; it is not a hosted live AI service. Normal processing sessions are temporary and cleared when the backend restarts.

## Deferred work

Accounts, durable research libraries, cross-session report history, topic alerts, shared team workspaces, hosted multi-user operation, OCR, more paper providers, citation-based discovery, automatic paper clustering, personalized researcher profiles, and research-design advice are outside this proof of concept.

Website integration and independent user validation were requested after the initial submission. Their plans and pending state are documented separately; they are not claimed as already delivered product capabilities.

## Team learning and division of work

The team learned to clarify requirements, separate a large feature into small tasks, and follow a planning → implementation → testing → feedback cycle. Work was divided by frontend interaction versus sources/processing/contracts, not by operating system. Each collaborator uses their own environment and credentials; virtual environments and API keys are not shared through Git.
