---
doc: spec
status: approved-architecture-with-current-implementation-notes
edition: current-English-consolidation
updated: 2026-10-24
---

# AI Radar — Technical Specification

This English edition consolidates the approved architecture and current source behavior. It replaces superseded planning assumptions in the public reading path, not the original development evidence. It does not turn earlier failed experiments into successful checks. See [scope](scope.md), [PRD](prd.md), and [delivery evidence](checklist.md).

## 1. Runtime and architecture

AI Radar is a local web application: React/TypeScript presents discovery, materials, reports, and evidence; a Python/FastAPI service retrieves papers, parses PDFs, manages jobs, calls the chosen model provider, and validates outputs. A production frontend build is served by the same backend. A separate Vite development server proxies API requests to the backend.

| Component | Implementation |
|---|---|
| Frontend | React, TypeScript, Vite; exact dependency versions in the lockfile |
| Report rendering | react-markdown, remark-gfm, remark-math, rehype-katex |
| Backend | Python 3.12+, FastAPI, Pydantic, asyncio |
| Sources | httpx requests to official arXiv API, PDFs, taxonomy-derived local index, and official statistics |
| PDF | pypdf; extractable text and original page bytes; no replacement OCR service |
| Providers | Explicit Qwen or Claude adapter; credentials stay on the backend |
| Storage | Temporary session files and in-memory collections/jobs/reports; persisted preferences/ranking state |
| Checks | pytest with synthetic fixtures/mocked calls; recorded real-paper generation and team acceptance are separate evidence |

Windows is the verified development/demo platform. macOS setup is supplied, but hardware execution remains optional and unverified. The public GitHub Pages site is a static demo player, not a remote instance of this backend.

## 2. Local setup

Use Python 3.12 or later and Node.js 22.12 or later. Create independent environments on each computer. Do not copy `.venv`, `node_modules`, or real keys between collaborators through Git.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
cd frontend
npm ci
npm run build
cd ..
./.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

### macOS Terminal

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
test -f .env || cp .env.example .env
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Edit the local `.env` with a valid chosen-provider key and arXiv contact email, then open `http://127.0.0.1:8000`. The template selects Qwen; the code fallback when no provider is configured is Claude. `AI_RADAR_PROVIDER` must explicitly be `qwen` or `claude`. Available model names/endpoints depend on the user's account; they are configuration values, not a promise of future provider availability.

Configuration includes provider/model/base URL, data directory, output/call limits, and development usage budget. The code defaults are not the team's historical account balance. A local usage estimate is not a provider bill. Existing budget-ledger validation can stop new work; do not delete/reset it to bypass a user limit. No automatic paid fallback to another provider is permitted.

## 3. Source acquisition and category mapping

`backend/app/sources/categories.py` resolves the checked-in official category index and helper aliases. Preserve official names/codes; aliases are search aids. Present ambiguous candidates. A chosen archive/group becomes an explicit union of valid subcategories, while a code such as `cs.AI` remains an exact subcategory query.

`sources/arxiv.py` uses the official Atom API with first-submission descending order and a frozen UTC cutoff. Parse paper identity, original title, abstract, first submission, update time, categories, and official PDF link. Remove version duplicates and entries later than the cutoff. Pagination/filtering can request more source entries than the final maximum of five. Do not replace removed failed papers with newly searched ones.

Serialize arXiv requests with the configured delay/contact identity; avoid two development machines making dense parallel requests. Validate official download destinations and report actual acquisition failures. Source errors are distinct from a valid empty result. Never silently change to another provider/site.

`sources/rankings.py` reads the official monthly archive chart and its official document source without executing remote JavaScript. Validate expected archive series, month, integer nonnegative counts, array lengths, and repeated values. In the chart, an archive's already-aggregated count can appear once per subcategory; do not sum those repetitions again.

Special mappings include `hep` to `hep-ex`, `hep-lat`, `hep-ph`, `hep-th`; `physics` to `physics`, `nlin`, `gr-qc`, `quant-ph`, `nucl-ex`, `nucl-th`. Other groups use their official archive/subcategory membership. Tests cover mapping and chart parsing. A layout change or mismatch fails explicitly rather than generating a guessed ranking.

Persist ranking attempts and valid month data. Automatic fetching stops after three total tries, with bounded delays; a manual request is one attempt. Verified snapshots retain their true month and snapshot label. Preferences use revision checks so stale saves do not silently replace newer changes.

Official references: [category taxonomy](https://arxiv.org/category_taxonomy), [API manual](https://info.arxiv.org/help/api/user-manual.html), [API terms](https://info.arxiv.org/help/api/tou.html), [monthly statistics](https://info.arxiv.org/about/reports/submission_category_by_year.html).

## 4. Materials, revisions, and temporary storage

Each collection has an identity, revision, and ordered materials. A material records identity/revision, source origin and actual content source, paper identity where applicable, original filename, byte size, SHA-256, page count/checks, warnings, readiness, and error.

Uploads accept at most 50 MiB per file and 1–150 pages. Reject invalid PDF signatures, encryption, damaged files, and files with no extractable text. Warn about individual textless pages; original PDF pages remain important for visual/equation review. A text extraction result is not OCR or scientific verification.

Replace an item using the same material identity and a new revision. Preserve its selected paper identity but record that the replacement's content came from an upload. Recheck collection revision after asynchronous file work before an atomic commit. Reject over-limit additions as a whole. Changes require the expected collection revision and are blocked while that collection has an active generation job; the user exits before editing.

One ready material selects single reading; two to ten ready materials select joint reading. Freeze the job's material snapshot and revisions when generation begins. Every final paper must be ready; no skipping, abstract substitution, or truncated joint collection is allowed.

`store.py` owns one backend process session with collections, files, jobs, reports, task handles, idempotency records, and evidence cache. Normal report/material sessions are temporary. Stale session cleanup is scoped to owned session directories. Settings, ranking data, and explicitly saved development review artifacts have separate lifecycles. The latter are not a user-facing research library.

## 5. Generation and source evidence

### Overview

The discovery job searches, acquires sources, optionally waits for source decisions, builds evidence, formats cards, checks them, and publishes on success. Only an explicit `use_abstract` decision enables an abstract-based overview for the specified unavailable full text. Keep its basis and failure reason visible. Missing abstract and full text permit removal or exit only.

Use fixed batch/card schemas and preserve retrieval order. The report includes each paper's actual covered pages, evidence, source warnings, and visual when available. Numeric and identifier checks must distinguish measured values from concept labels, figure locators, and teaching examples; unsupported result numbers remain failures.

For newer papers, `reading/overview_scene.py` can produce a source-linked three-step scene plan, validate its allowed schema/evidence IDs, and independently audit it before rendering escaped labels with code-owned SVG shapes. It does not execute model-generated SVG/HTML. Scene labels cannot introduce measured numbers or links. A failed scene can be omitted with a warning while verified text remains. Earlier saved samples also have reviewed paper-ID-specific static scenes. Both paths are explanatory illustrations, not paper figures or experimental results; successful generation for a sample does not prove universal visual coverage.

### Single and joint reading

Retain original PDF pages and page text, extract source evidence, build a structured fact/concept basis, then generate the relevant report template. Longer documents are processed in page segments rather than silently truncating the whole paper. Track page coverage and offsets back to original physical pages. Provider/request/context limits may still cause a visible failure.

Claude's native citation path and Qwen's selected-evidence path differ. Do not describe Qwen evidence as native Claude citations. Reports refer to retained evidence IDs; source locations come from retained records, not freely invented model citation objects. A valid evidence ID proves a reference exists, not that a scientific claim is entailed by it.

The single-paper learning path uses extraction, a prerequisite/research map, section/individual-equation writing, assembly, and independent quality review. Markdown inside controlled tags avoids forcing LaTeX through fragile JSON escaping. Equation corrections use constrained field patches with a fixed equation identity; null fields retain original bytes, and formula/source identities cannot be silently rewritten. Local validation and final review run again after merging.

Joint reading has its own six-part comparative template and must represent every selected material. Keep original experimental tasks, metrics, datasets, and conditions; explicitly mark incomparable results and cross-paper inferences. Partial processing must not be presented as complete joint reading.

### Quality review and language conversion

Validate schema, required sections/order, complete material coverage, source IDs/page ranges, numerical conditions, language fields, and complete model responses. Truncated/refused/malformed output is not success. Bounded targeted repair is permitted; no infinite automatic paid rewrite loop. Review findings must be checked against current report text and quoted source evidence so reviewer mistakes do not automatically become paper facts.

Separate hard format/source/usability constraints from soft prose targets. The team's completion-first revision relaxed excessive verbosity and presentation demands, not evidence or formatting requirements. Scientific accuracy still needs human source checks even after automated review.

Interface language changes are local UI operations. Report-language jobs reuse the report's source/fact basis, preserve paper identities/numbers/conditions/citations, and generate aligned Chinese/English/bilingual text. Reuse a compatible existing variant when available; do not retrieve a new paper set to translate an existing report. Failed language preservation must remain a failure.

## 6. Jobs, concurrency, and API contracts

Async jobs keep HTTP requests short. Jobs expose identity, kind, phase, status, progress, selected snapshot, language, usage, error, and resulting report identity. Core states include queued, running, awaiting decision where applicable, succeeded, failed, and cancelled. A backend AI lock serializes expensive report work. Cancelled/abandoned jobs cannot publish late output into a newer UI view.

Create-model-job endpoints require an `Idempotency-Key`. Reusing a key for a different payload is a conflict; repeated compatible starts return the existing job. Collection edits require `expected_revision`. Stale revisions, active-job edits, unavailable sessions, and invalid selections fail explicitly.

| Method / route | Role |
|---|---|
| `GET /api/v1/health` | Status, provider/model configuration indicator, session identity; never API key |
| `GET /api/v1/categories` | Valid category candidates |
| `GET`, `PUT /api/v1/settings` | Read/update persisted preferences with revision control |
| `GET /api/v1/rankings` | Ranking data and attempt state |
| `POST /api/v1/rankings/fetch` | One manual fetch |
| `POST /api/v1/overview-jobs` | Start category discovery/overview |
| `POST /api/v1/jobs/{job_id}/decisions` | Submit failed-source decisions |
| `POST /api/v1/collections` | Create empty collection or selected overview collection |
| `GET /api/v1/collections/{collection_id}` | Current materials/revision |
| `POST /api/v1/collections/{collection_id}/uploads` | Add uploaded PDFs |
| `PUT /api/v1/collections/{collection_id}/materials/{material_id}/file` | Replace one material |
| `DELETE /api/v1/collections/{collection_id}/materials/{material_id}` | Remove one material |
| `GET /api/v1/materials/{material_id}/pdf` | Read PDF for the expected revision |
| `POST /api/v1/reading-jobs` | Start explicit single/joint reading |
| `GET /api/v1/jobs/{job_id}` | Poll progress/result/error |
| `POST /api/v1/jobs/{job_id}/cancel` | Exit/cancel current task |
| `POST /api/v1/jobs/{job_id}/retry` | Explicit compatible retry |
| `GET /api/v1/reports/{report_id}` | Structured report |
| `POST /api/v1/reports/{report_id}/language-jobs` | Translate the same report basis |
| `GET /api/v1/reports/{report_id}/pdf` | Original report PDF access |

Success responses use `{data, request_id}`; errors use `{error, request_id}` with stable code/message/retryability. Requests include request IDs and no-store responses. Frontend type contracts are in `frontend/src/api/` and request models in `backend/app/models/`.

## 7. Source layout and two-person tasks

| Path | Responsibility |
|---|---|
| `frontend/src/pages/` | Homepage/discovery and reading interactions |
| `frontend/src/api/` | Typed API client/contracts |
| `backend/app/main.py` | Routes, request validation, coordination |
| `backend/app/sources/` | arXiv retrieval, category index, monthly rankings |
| `backend/app/documents/` | PDF validation, text and page splitting |
| `backend/app/reading/` | Providers, evidence, jobs, templates, review, language, scenes |
| `backend/app/prompts/` | Versioned generation contracts/templates |
| `backend/app/store.py` | Temporary sessions and revision safety |
| `tests/` | Fixtures and automated checks |
| `devpost/` | English planning, delivery evidence, and user-validation protocol |

One teammate can own frontend flow/state/localization and the other source acquisition/PDF/evidence/generation. Agree API fields and error codes before parallel edits. Small handoffs are category selection, source decisions, collection editing, report display, evidence inspection, language switching, and recovery. Both review the integrated journey; operating system does not determine ownership. Pull before work; commit/push reviewed changes before switching computers. Keep secrets and generated private material out of commits.

## 8. Verification and limitations

The October 24 Windows recheck of the public source passed all 216 backend tests and the frontend production build, with a nonblocking bundle-size warning. The earlier October 18 results remain historical evidence. The rerun used the existing Python environment and a fresh installation of locked frontend dependencies; it was not a clean-machine installation test. Mocked tests do not prove model quality, live provider availability, or time saved. Real saved samples and first-party feedback are documented separately. macOS hardware verification remains unperformed. Owner-reported retrospective hands-on feedback now records a mixed team/non-team group and qualitative observations; exact count/dates and individual task outcomes remain unknown.

Test boundaries include zero/few results, malformed/unavailable sources, abstract decisions, PDF limits, collection revisions, ten-paper limits, cancellation/retry, source/number checks, ranking mapping/retry stop, and language preservation. Inspect report math and evidence manually; neither a model review label nor test count certifies scientific accuracy.

No production authentication, per-user isolation, distributed queue, public model-spend protection, OCR, or durable research history is implemented. A public live deployment requires additional work and cannot safely be obtained by merely exposing the local port. Do not place a provider API key in browser code or GitHub Pages.

## 9. Sharing and website integration

- Public source: https://github.com/ChuangHu07/ai-radar
- English video: https://youtu.be/1sG9wfRfSuk
- Static player: https://chuanghu07.github.io/ai-radar/
- Devpost entry: https://devpost.com/software/ai101
- Original project code: MIT License; third-party components retain their own licenses.

Credentials, personal learner profile, source PDFs, private saved reports, ledgers, and private development Git history are excluded from publication. Historical Chinese planning remains recoverable in prior Git revisions; current public planning is consolidated in English.

A website can immediately link to or embed the existing video without running AI inference. Live in-site use needs a reachable backend, HTTPS/origin configuration, appropriate user/session isolation, upload handling, spend controls, and a decision on data retention. The owner has deferred website/cloud integration to prioritize the submission and feedback documentation. No live integration is claimed or required as a new artifact for this revision.
